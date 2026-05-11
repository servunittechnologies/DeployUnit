"""Authentication routes."""
import asyncio
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from pymongo import ReturnDocument

from db import get_db
from models import RegisterIn, LoginIn, UserOut
from auth_utils import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    set_auth_cookies, clear_auth_cookies,
    get_current_user,
)
from slugify import slugify
from services.emails import send_welcome, send_password_reset_link

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_public(u: dict) -> dict:
    return {
        "id": u["id"],
        "email": u["email"],
        "name": u.get("name", ""),
        "role": u.get("role", "user"),
        "github_login": u.get("github_login"),
        "github_avatar_url": u.get("github_avatar_url"),
        "created_at": u.get("created_at"),
    }


def _email_query(email: str) -> dict:
    """Match the user with case-insensitive email lookup."""
    raw = email.strip()
    lower = raw.lower()
    return {"$or": [{"email": raw}, {"email": lower}, {"email_ci": lower}]}


async def _bootstrap_workspace_for(user: dict):
    db = get_db()
    has = await db.workspace_members.find_one({"user_id": user["id"]})
    if has:
        return
    ws_id = str(uuid.uuid4())
    base_slug = slugify(f"{user['name'] or 'workspace'}-{user['id'][:6]}")
    await db.workspaces.insert_one(
        {
            "id": ws_id,
            "name": f"{user['name'].split(' ')[0] if user['name'] else 'My'} Workspace",
            "slug": base_slug,
            "type": "solo",
            "owner_id": user["id"],
            "plan": "free",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    await db.workspace_members.insert_one(
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "user_id": user["id"],
            "role": "owner",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


@router.post("/register", response_model=UserOut)
async def register(payload: RegisterIn, response: Response, background: BackgroundTasks):
    db = get_db()
    email_in = payload.email.strip()
    email_ci = email_in.lower()

    # Case-insensitive duplicate check first (so we always 400 on dups)
    if await db.users.find_one(_email_query(email_in)):
        raise HTTPException(status_code=400, detail="Email already registered")
    # Manual length validation so we surface a 400 (not Pydantic's 422)
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user = {
        "id": str(uuid.uuid4()),
        "email": email_in,        # preserve original case for display
        "email_ci": email_ci,     # case-insensitive index
        "password_hash": hash_password(payload.password),
        "name": payload.name.strip(),
        "role": "user",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user)
    user.pop("_id", None)
    await _bootstrap_workspace_for(user)
    access = create_access_token(user["id"], user["email"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    # Fire-and-forget welcome email. If MailerSend isn't configured, this no-ops.
    background.add_task(send_welcome, user)
    from services.audit import log as audit_log
    audit_log(action="auth.register", actor=user, resource_type="user", resource_id=user["id"])
    return _user_public(user)


@router.post("/login", response_model=UserOut)
async def login(payload: LoginIn, request: Request, response: Response):
    db = get_db()
    email_in = payload.email.strip()
    # Use the originating client IP from X-Forwarded-For (set by k8s ingress / cloudflare).
    xff = request.headers.get("x-forwarded-for", "")
    real_ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")
    identifier = f"{real_ip}:{email_in.lower()}"
    now = datetime.now(timezone.utc)

    # Existing lockout?
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= 5:
        locked_at = attempt.get("locked_at")
        if locked_at:
            locked_dt = datetime.fromisoformat(locked_at) if isinstance(locked_at, str) else locked_at
            if (now - locked_dt).total_seconds() < 900:
                raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 min.")

    user = await db.users.find_one(_email_query(email_in))
    if not user or not verify_password(payload.password, user["password_hash"]):
        # Increment counter atomically and return 429 the moment we cross 5.
        updated = await db.login_attempts.find_one_and_update(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_at": now.isoformat()}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if updated and updated.get("count", 0) >= 5:
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 min.")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await db.login_attempts.delete_one({"identifier": identifier})
    await _bootstrap_workspace_for(user)
    access = create_access_token(user["id"], user["email"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    from services.audit import log as audit_log
    audit_log(action="auth.login", actor=user, request=request)
    return _user_public(user)


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(request: Request):
    user = await get_current_user(request)
    return _user_public(user)


# ─────────────────────── Forgot password (self-serve) ───────────────────────
class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordIn, request: Request, background: BackgroundTasks):
    """Issue a one-time reset link by email. Always returns 200 even if the
    email is unknown — don't leak which addresses are registered."""
    db = get_db()
    user = await db.users.find_one(_email_query(payload.email))
    # Always respond identically to prevent enumeration.
    if user:
        token = secrets.token_urlsafe(40)
        expires = datetime.now(timezone.utc) + timedelta(minutes=60)
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "reset_token": token,
                "reset_token_expires_at": expires.isoformat(),
            }},
        )
        frontend = (request.headers.get("origin") or "").rstrip("/")
        if not frontend:
            import os as _os
            frontend = (_os.environ.get("FRONTEND_URL") or "").rstrip("/")
        reset_url = f"{frontend}/reset-password?token={token}"
        background.add_task(send_password_reset_link, user, reset_url, 60)
        from services.audit import log as audit_log
        audit_log(action="auth.forgot_password_request", actor=user,
                  meta={"email": user["email"]}, request=request)
    return {"ok": True, "message": "If that email exists, a reset link is on its way."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordIn, request: Request):
    """Consume a one-time token and set a new password."""
    db = get_db()
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    user = await db.users.find_one({"reset_token": payload.token})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    expires = user.get("reset_token_expires_at")
    if expires:
        try:
            dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        except Exception:
            dt = None
        if dt and dt < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Reset token has expired")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "password_hash": hash_password(payload.new_password),
            "password_updated_at": datetime.now(timezone.utc).isoformat(),
        }, "$unset": {"reset_token": "", "reset_token_expires_at": ""}},
    )
    from services.audit import log as audit_log
    audit_log(action="auth.password_reset_self", actor=user,
              resource_type="user", resource_id=user["id"], request=request)
    return {"ok": True}

