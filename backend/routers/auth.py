"""Authentication routes."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Response
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

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_public(u: dict) -> dict:
    return {
        "id": u["id"],
        "email": u["email"],
        "name": u.get("name", ""),
        "role": u.get("role", "user"),
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
            "plan": "hobby",
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
async def register(payload: RegisterIn, response: Response):
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
    return _user_public(user)


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(request: Request):
    user = await get_current_user(request)
    return _user_public(user)
