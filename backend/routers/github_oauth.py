"""GitHub OAuth — social sign-in + repo connection."""
import os
import uuid
import secrets
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from slugify import slugify

from db import get_db
from auth_utils import (
    create_access_token, create_refresh_token, set_auth_cookies,
    get_current_user,
)
from crypto_utils import encrypt_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/github", tags=["auth"])

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_USER_EMAILS_URL = "https://api.github.com/user/emails"
GITHUB_SCOPES = "read:user user:email repo"


def _frontend_origin() -> str:
    fe = os.environ.get("FRONTEND_URL", "")
    return fe.rstrip("/") if fe else ""


def _request_origin(request: Request) -> str:
    """Best-effort recovery of the public origin the user hit us on.

    We trust X-Forwarded-* headers because we always sit behind an ingress.
    Falls back to the request URL, and finally to FRONTEND_URL.
    """
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.hostname
    )
    proto = (
        request.headers.get("x-forwarded-proto")
        or request.url.scheme
        or "https"
    )
    if host:
        return f"{proto}://{host}".rstrip("/")
    return _frontend_origin()


def _redirect_uri_for(origin: str) -> str:
    """OAuth callback URL bound to the given origin (preview, prod, or custom domain)."""
    return f"{origin.rstrip('/')}/api/auth/github/callback"


def _redirect_uri() -> str:
    # Static default for legacy callers; prefer _redirect_uri_for(origin).
    return f"{_frontend_origin()}/api/auth/github/callback"


def _client_credentials() -> tuple[str, str]:
    cid = os.environ.get("GITHUB_CLIENT_ID")
    secret = os.environ.get("GITHUB_CLIENT_SECRET")
    if not cid or not secret:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
    return cid, secret


@router.get("/start")
async def github_start(request: Request, redirect_to: Optional[str] = None, link: bool = False):
    """Begin OAuth: returns the GitHub authorize URL after stashing a state token.

    Query params:
      - redirect_to: 'new_app' to send the user to /app/apps/new after auth, otherwise /app
      - link: if true and the caller is already authenticated, attach GitHub to their existing user
    """
    cid, _ = _client_credentials()
    db = get_db()

    # If link=true, capture the calling user's id so we attach to their account.
    link_user_id = None
    if link:
        try:
            current = await get_current_user(request)
            link_user_id = current["id"]
        except HTTPException:
            link_user_id = None  # not authenticated, treat as fresh sign-in

    state = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    # Bind this OAuth round-trip to the origin the user is on RIGHT NOW
    # (preview, production, or any future custom domain). The callback will
    # use the same values so the GitHub token exchange's redirect_uri matches
    # and the final RedirectResponse lands on the correct frontend.
    origin = _request_origin(request)
    redirect_uri = _redirect_uri_for(origin)
    await db.oauth_states.insert_one(
        {
            "id": str(uuid.uuid4()),
            "state": state,
            "redirect_to": redirect_to or "app",
            "link_user_id": link_user_id,
            "origin": origin,
            "redirect_uri": redirect_uri,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=10)).isoformat(),
        }
    )

    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "scope": GITHUB_SCOPES,
        "state": state,
        "allow_signup": "true",
    }
    return JSONResponse({"authorization_url": f"{GITHUB_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"})


async def _exchange_code(code: str, redirect_uri: str) -> str:
    cid, secret = _client_credentials()
    async with httpx.AsyncClient(timeout=15.0) as cli:
        r = await cli.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": cid,
                "client_secret": secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
    if r.status_code != 200:
        logger.warning("GitHub token exchange %s %s", r.status_code, r.text[:200])
        raise HTTPException(status_code=400, detail="GitHub token exchange failed")
    body = r.json()
    if not body.get("access_token"):
        raise HTTPException(status_code=400, detail=body.get("error_description") or "No access token")
    return body["access_token"]


async def _fetch_github_user(token: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as cli:
        u = await cli.get(GITHUB_USER_URL, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        })
        if u.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch GitHub user")
        gh_user = u.json()

        # Resolve email — primary verified > any verified > public
        email = gh_user.get("email")
        e = await cli.get(GITHUB_USER_EMAILS_URL, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        })
        if e.status_code == 200:
            emails = e.json() or []
            primary = next((x["email"] for x in emails if x.get("primary") and x.get("verified")), None)
            verified = next((x["email"] for x in emails if x.get("verified")), None)
            email = primary or verified or email
        gh_user["resolved_email"] = email
    return gh_user


def _bootstrap_workspace_payload(name: str, owner_id: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "name": f"{name.split(' ')[0] if name else 'My'} Workspace",
        "slug": slugify(f"{name or 'workspace'}-{owner_id[:6]}"),
        "type": "solo",
        "owner_id": owner_id,
        "plan": "free",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/callback")
async def github_callback(code: str, state: str, request: Request):
    db = get_db()

    state_doc = await db.oauth_states.find_one({"state": state})
    # Resolve the origin we should redirect the user back to. Prefer the
    # origin captured at /start (so prod stays prod, preview stays preview),
    # fall back to the current request, and finally to FRONTEND_URL.
    if state_doc and state_doc.get("origin"):
        fe = state_doc["origin"].rstrip("/")
    else:
        fe = _request_origin(request) or _frontend_origin()

    if not state_doc:
        return RedirectResponse(url=f"{fe}/login?error=oauth_invalid_state", status_code=302)
    expires_at = state_doc.get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
        await db.oauth_states.delete_one({"state": state})
        return RedirectResponse(url=f"{fe}/login?error=oauth_state_expired", status_code=302)
    await db.oauth_states.delete_one({"state": state})

    redirect_uri = state_doc.get("redirect_uri") or _redirect_uri_for(fe)

    try:
        token = await _exchange_code(code, redirect_uri)
        gh_user = await _fetch_github_user(token)
    except HTTPException:
        return RedirectResponse(url=f"{fe}/login?error=oauth_failed", status_code=302)
    except Exception as e:
        logger.exception("oauth callback failure: %s", e)
        return RedirectResponse(url=f"{fe}/login?error=oauth_failed", status_code=302)

    gh_id = gh_user.get("id")
    gh_login = gh_user.get("login")
    gh_email = gh_user.get("resolved_email") or f"{gh_login}@users.noreply.github.com"
    gh_avatar = gh_user.get("avatar_url")
    encrypted = encrypt_token(token)

    link_user_id = state_doc.get("link_user_id")
    user = None
    if link_user_id:
        user = await db.users.find_one({"id": link_user_id})

    if user is None:
        # Try by github_user_id
        user = await db.users.find_one({"github_user_id": gh_id})

    if user is None and gh_email:
        # Try by email (case-insensitive)
        user = await db.users.find_one({"$or": [
            {"email": gh_email},
            {"email": gh_email.lower()},
            {"email_ci": gh_email.lower()},
        ]})

    if user is None:
        # Create new user
        new_id = str(uuid.uuid4())
        user = {
            "id": new_id,
            "email": gh_email,
            "email_ci": gh_email.lower() if gh_email else None,
            "password_hash": "",  # OAuth-only; password reset can populate later
            "name": gh_user.get("name") or gh_login,
            "role": "user",
            "github_user_id": gh_id,
            "github_login": gh_login,
            "github_avatar_url": gh_avatar,
            "github_access_token": encrypted,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user)
        # Bootstrap workspace
        ws = _bootstrap_workspace_payload(user["name"] or gh_login, new_id)
        await db.workspaces.insert_one(ws)
        await db.workspace_members.insert_one({
            "id": str(uuid.uuid4()),
            "workspace_id": ws["id"],
            "user_id": new_id,
            "role": "owner",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "github_user_id": gh_id,
                "github_login": gh_login,
                "github_avatar_url": gh_avatar,
                "github_access_token": encrypted,
            }},
        )
        # Make sure they have a workspace
        has = await db.workspace_members.find_one({"user_id": user["id"]})
        if not has:
            ws = _bootstrap_workspace_payload(user.get("name") or gh_login, user["id"])
            await db.workspaces.insert_one(ws)
            await db.workspace_members.insert_one({
                "id": str(uuid.uuid4()),
                "workspace_id": ws["id"],
                "user_id": user["id"],
                "role": "owner",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    # Issue our session cookies + redirect to frontend
    redirect_to = state_doc.get("redirect_to") or "app"
    target = "/app/apps/new" if redirect_to == "new_app" else "/app"
    response = RedirectResponse(url=f"{fe}{target}", status_code=302)
    access = create_access_token(user["id"], user["email"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return response


@router.post("/disconnect")
async def github_disconnect(request: Request):
    user = await get_current_user(request)
    db = get_db()
    await db.users.update_one(
        {"id": user["id"]},
        {"$unset": {"github_access_token": "", "github_login": "", "github_user_id": "", "github_avatar_url": ""}},
    )
    return {"ok": True}
