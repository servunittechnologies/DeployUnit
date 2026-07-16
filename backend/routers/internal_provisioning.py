"""Internal provisioning API — consumed by the ServUnit WHMCS billing system.

WHMCS owns the commercial lifecycle (orders, invoices, dunning). When a
customer buys a plan there, WHMCS calls these endpoints to create the
DeployUnit account exactly like a native signup (user + bootstrap workspace +
welcome email + set-password link), assign the plan, and later to suspend,
unsuspend, change plan or terminate. `POST /internal/sso` hands the customer
a one-time login URL so "Open DeployUnit" in the WHMCS client area lands them
authenticated in the dashboard (same cookie mechanics as the GitHub OAuth
callback).

Auth: every endpoint except `GET /internal/sso/consume` (hit by the customer's
browser) requires the `X-Internal-Key` header to match env `INTERNAL_API_KEY`.
With the env var unset the API is fully disabled (fails closed).

Billing note: users provisioned here get `billing_managed_by: "whmcs"`; plan
changes deliberately never touch Mollie — WHMCS is the payment system.
"""

import asyncio
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from auth_utils import create_access_token, create_refresh_token, set_auth_cookies
from clients.coolify import coolify
from db import get_db
from routers.auth import _bootstrap_workspace_for, _email_query
from services.audit import log as audit_log
from services.emails import send_password_reset_link, send_welcome
from services.plans import account_usage, get_plan

router = APIRouter(prefix="/internal", tags=["internal"])

SSO_TOKEN_TTL_SECONDS = 120
SET_PASSWORD_TTL_MINUTES = 60 * 24 * 7  # provisioning mail may sit unread for days


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _frontend_url() -> str:
    return (os.environ.get("FRONTEND_URL") or os.environ.get("PUBLIC_FRONTEND_URL") or "https://deployunit.com").rstrip("/")


def _require_internal_key(request: Request) -> None:
    configured = os.environ.get("INTERNAL_API_KEY", "")
    provided = request.headers.get("X-Internal-Key", "")
    if not configured or not provided or not hmac.compare_digest(configured, provided):
        raise HTTPException(status_code=403, detail="Forbidden")


async def _find_user(external_ref: Optional[str], email: Optional[str]) -> Optional[dict]:
    """Prefer the WHMCS service link; fall back to e-mail."""
    db = get_db()
    if external_ref:
        user = await db.users.find_one({"whmcs_service_id": str(external_ref)}, {"_id": 0})
        if user:
            return user
    if email:
        user = await db.users.find_one(_email_query(email), {"_id": 0})
        if user:
            return user
    return None


async def _require_user(external_ref: Optional[str], email: Optional[str]) -> dict:
    user = await _find_user(external_ref, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _owned_app_uuids(user_id: str) -> list[str]:
    db = get_db()
    ws_ids = await db.workspaces.distinct("id", {"owner_id": user_id})
    if not ws_ids:
        return []
    uuids: list[str] = []
    async for app in db.apps.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0, "coolify_app_uuid": 1}):
        if app.get("coolify_app_uuid"):
            uuids.append(app["coolify_app_uuid"])
    return uuids


async def _cancel_mollie_subscription(user_id: str) -> None:
    """Best-effort cancellation of a pre-existing self-billing subscription
    when an account is taken over by WHMCS. Never raises."""
    db = get_db()
    sub = await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0})
    if not sub or not sub.get("mollie_subscription_id") or not sub.get("mollie_customer_id"):
        return
    if sub.get("status") == "canceled":
        return
    try:
        from clients.mollie import mollie
        if mollie.configured:
            await mollie.cancel_subscription(sub["mollie_customer_id"], sub["mollie_subscription_id"])
        await db.subscriptions.update_one(
            {"id": sub["id"]},
            {"$set": {"status": "canceled", "canceled_reason": "whmcs_takeover"}},
        )
    except Exception as e:  # noqa: BLE001 — takeover must not fail on Mollie
        import logging
        logging.getLogger("deployunit").warning("whmcs takeover: mollie cancel failed for %s: %s", user_id, e)


async def _set_plan(user: dict, plan_id: str) -> dict:
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan '{plan_id}'")
    db = get_db()
    now = _now_iso()
    # users.plan is the source of truth; workspaces.plan is the legacy mirror
    # (same convention as routers/admin_users.set_plan). Mollie is untouched
    # on purpose — WHMCS bills these accounts.
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"plan": plan["id"], "plan_changed_at": now}},
    )
    await db.workspaces.update_many(
        {"owner_id": user["id"]},
        {"$set": {"plan": plan["id"], "plan_changed_at": now}},
    )
    return plan


# ─────────────────────── Plans (also the WHMCS Test Connection target) ───────────────────────

@router.get("/plans")
async def internal_list_plans(request: Request):
    _require_internal_key(request)
    db = get_db()
    plans = await db.platform_plans.find({"active": {"$ne": False}}, {"_id": 0}).sort("order", 1).to_list(50)
    return {
        "plans": [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "price_eur": p.get("price"),
                "limits": p.get("limits"),
                "credits": p.get("credits"),
            }
            for p in plans
        ]
    }


# ─────────────────────── Provision ───────────────────────

class ProvisionIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    plan: str = "free"
    external_ref: str = Field(min_length=1, max_length=64)  # WHMCS service id
    send_emails: bool = True


@router.post("/provision")
async def provision(payload: ProvisionIn, request: Request, background: BackgroundTasks):
    """Create (or link) the DeployUnit account for a WHMCS service.

    Idempotent: re-running for the same external_ref/e-mail updates the plan
    and returns the existing ids instead of failing.
    """
    _require_internal_key(request)
    db = get_db()

    plan = await get_plan(payload.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan '{payload.plan}'")

    user = await _find_user(payload.external_ref, payload.email)
    created = False

    if not user:
        # Mirrors routers/auth.register — but SSO/e-mail-first: no password
        # yet (like GitHub OAuth users), the customer sets one via the link.
        user = {
            "id": str(uuid.uuid4()),
            "email": payload.email.strip(),
            "email_ci": payload.email.strip().lower(),
            "password_hash": "",
            "name": payload.name.strip(),
            "role": "user",
            "created_at": _now_iso(),
            "billing_managed_by": "whmcs",
            "whmcs_service_id": str(payload.external_ref),
            "is_active": True,
            "credits_balance": int(plan.get("credits") or 0),
            "credits_period_start": _now_iso(),
            "credits_granted_total": int(plan.get("credits") or 0),
        }
        await db.users.insert_one(user)
        user.pop("_id", None)
        created = True
    else:
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "billing_managed_by": "whmcs",
                "whmcs_service_id": str(payload.external_ref),
                "is_active": True,
            }},
        )
        # If this e-mail already self-billed via Mollie, cancel that
        # subscription so WHMCS takes over cleanly — no double billing.
        await _cancel_mollie_subscription(user["id"])

    await _bootstrap_workspace_for(user)
    await _set_plan(user, plan["id"])

    if created and payload.send_emails:
        token = secrets.token_urlsafe(40)
        expires = datetime.now(timezone.utc) + timedelta(minutes=SET_PASSWORD_TTL_MINUTES)
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"reset_token": token, "reset_token_expires_at": expires.isoformat()}},
        )
        reset_url = f"{_frontend_url()}/reset-password?token={token}"
        background.add_task(send_welcome, user)
        background.add_task(send_password_reset_link, user, reset_url, SET_PASSWORD_TTL_MINUTES)

    workspace = await db.workspaces.find_one({"owner_id": user["id"]}, {"_id": 0, "id": 1, "name": 1})
    audit_log(action="internal.provision", actor=user, resource_type="user", resource_id=user["id"],
              meta={"external_ref": payload.external_ref, "plan": plan["id"], "created": created}, request=request)

    return {
        "ok": True,
        "created": created,
        "user_id": user["id"],
        "email": user["email"],
        "workspace_id": (workspace or {}).get("id"),
        "plan": plan["id"],
    }


# ─────────────────────── Plan change ───────────────────────

class PlanChangeIn(BaseModel):
    external_ref: Optional[str] = None
    email: Optional[EmailStr] = None
    plan: str


@router.post("/plan")
async def change_plan(payload: PlanChangeIn, request: Request):
    _require_internal_key(request)
    user = await _require_user(payload.external_ref, payload.email)
    plan = await _set_plan(user, payload.plan)
    audit_log(action="internal.plan_change", actor=user, resource_type="user", resource_id=user["id"],
              meta={"external_ref": payload.external_ref, "plan": plan["id"]}, request=request)
    return {"ok": True, "user_id": user["id"], "plan": plan["id"]}


# ─────────────────────── Suspend / Unsuspend ───────────────────────

class UserRefIn(BaseModel):
    external_ref: Optional[str] = None
    email: Optional[EmailStr] = None


@router.post("/suspend")
async def suspend(payload: UserRefIn, request: Request):
    """Blocks dashboard access (is_active=False, enforced in get_current_user)
    and stops the customer's running apps. Best-effort on Coolify: one dead
    container must not fail the WHMCS suspension."""
    _require_internal_key(request)
    db = get_db()
    user = await _require_user(payload.external_ref, payload.email)
    await db.users.update_one({"id": user["id"]}, {"$set": {"is_active": False}})
    stopped = 0
    for app_uuid in await _owned_app_uuids(user["id"]):
        try:
            await coolify.stop(app_uuid)
            stopped += 1
        except Exception:
            pass
    audit_log(action="internal.suspend", actor=user, resource_type="user", resource_id=user["id"],
              meta={"external_ref": payload.external_ref, "apps_stopped": stopped}, request=request)
    return {"ok": True, "user_id": user["id"], "apps_stopped": stopped}


@router.post("/unsuspend")
async def unsuspend(payload: UserRefIn, request: Request):
    _require_internal_key(request)
    db = get_db()
    user = await _require_user(payload.external_ref, payload.email)
    await db.users.update_one({"id": user["id"]}, {"$set": {"is_active": True}})
    started = 0
    for app_uuid in await _owned_app_uuids(user["id"]):
        try:
            await coolify.restart(app_uuid)
            started += 1
        except Exception:
            pass
    audit_log(action="internal.unsuspend", actor=user, resource_type="user", resource_id=user["id"],
              meta={"external_ref": payload.external_ref, "apps_started": started}, request=request)
    return {"ok": True, "user_id": user["id"], "apps_started": started}


# ─────────────────────── Terminate ───────────────────────

class TerminateIn(BaseModel):
    external_ref: Optional[str] = None
    email: Optional[EmailStr] = None
    delete_user: bool = False


@router.post("/terminate")
async def terminate(payload: TerminateIn, request: Request):
    """Tears down every owned workspace (apps, databases, subdomains, Coolify
    resources — same cascade as workspace force-delete) and deactivates or
    deletes the account. Idempotent: an already-gone user returns ok."""
    _require_internal_key(request)
    db = get_db()
    user = await _find_user(payload.external_ref, payload.email)
    if not user:
        return {"ok": True, "already_gone": True}

    from services.github_webhooks import unregister_webhook as wh_unregister
    from services.subdomains import release_subdomain

    workspaces = await db.workspaces.find({"owner_id": user["id"]}, {"_id": 0, "id": 1, "coolify_project_uuid": 1}).to_list(50)
    ws_ids = [w["id"] for w in workspaces]
    project_uuids = [w.get("coolify_project_uuid") for w in workspaces if w.get("coolify_project_uuid")]
    apps_deleted = 0
    for ws_id in ws_ids:
        apps = await db.apps.find({"workspace_id": ws_id}).to_list(500)
        for app in apps:
            if app.get("cloudflare_dns_record_id"):
                try:
                    await release_subdomain(app)
                except Exception:
                    pass
            if app.get("webhook_github_id"):
                try:
                    await wh_unregister(app=app, workspace_id=ws_id)
                except Exception:
                    pass
            if app.get("coolify_app_uuid"):
                try:
                    await coolify.delete_application(app["coolify_app_uuid"])
                except Exception:
                    pass
            apps_deleted += 1
        dbs = await db.databases.find({"workspace_id": ws_id}).to_list(200)
        for d in dbs:
            if d.get("coolify_db_uuid"):
                try:
                    await coolify.delete_database(d["coolify_db_uuid"])
                except Exception:
                    pass
        for collection in ("apps", "deployments", "domains", "databases", "cron_jobs", "pr_previews"):
            await db[collection].delete_many({"workspace_id": ws_id})
        await db.workspaces.delete_one({"id": ws_id})
        await db.workspace_members.delete_many({"workspace_id": ws_id})
        await db.subscriptions.delete_many({"workspace_id": ws_id})
        await db.billing_profiles.delete_many({"workspace_id": ws_id})

    # Best-effort: remove the now-empty Coolify projects. App deletion is
    # async in Coolify, so retry briefly while it refuses ("has resources").
    for project_uuid in project_uuids:
        for attempt in range(6):
            try:
                _data, status_code, _err = await coolify.delete_project(project_uuid)
                if status_code in (200, 204, 404) or status_code == 0:
                    break
            except Exception:
                break
            await asyncio.sleep(5)

    if payload.delete_user:
        await db.workspace_members.delete_many({"user_id": user["id"]})
        await db.users.delete_one({"id": user["id"]})
    else:
        # Detach from WHMCS: suspended + free + back to self-billing, so if the
        # same person returns (new WHMCS order or standalone) they're a clean
        # account, not a WHMCS orphan.
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"is_active": False, "plan": "free", "plan_changed_at": _now_iso(),
                      "billing_managed_by": "self"},
             "$unset": {"whmcs_service_id": ""}},
        )

    audit_log(action="internal.terminate", actor=user, resource_type="user", resource_id=user["id"],
              meta={"external_ref": payload.external_ref, "workspaces": len(ws_ids),
                    "apps": apps_deleted, "user_deleted": payload.delete_user}, request=request)
    return {"ok": True, "workspaces_removed": len(ws_ids), "apps_removed": apps_deleted,
            "user_deleted": payload.delete_user}


# ─────────────────────── Status (WHMCS admin tab / client area) ───────────────────────

@router.get("/status")
async def status(request: Request, external_ref: Optional[str] = None, email: Optional[str] = None):
    _require_internal_key(request)
    db = get_db()
    user = await _require_user(external_ref, email)
    usage = await account_usage(user["id"])
    plan = await get_plan(user.get("plan") or "free")
    workspaces = await db.workspaces.find(
        {"owner_id": user["id"]}, {"_id": 0, "id": 1, "name": 1, "slug": 1, "type": 1}
    ).to_list(50)
    return {
        "user_id": user["id"],
        "email": user["email"],
        "name": user.get("name"),
        "is_active": user.get("is_active", True),
        "plan": {
            "id": (plan or {}).get("id"),
            "name": (plan or {}).get("name"),
            "limits": (plan or {}).get("limits"),
        },
        "usage": usage,
        "credits_balance": int(user.get("credits_balance") or 0),
        "workspaces": workspaces,
    }


# ─────────────────────── SSO ───────────────────────

class SsoIn(BaseModel):
    external_ref: Optional[str] = None
    email: Optional[EmailStr] = None
    return_to: str = "/app"


@router.post("/sso")
async def create_sso_link(payload: SsoIn, request: Request):
    """Returns a one-time, short-lived login URL for the WHMCS client area
    button. The customer's browser hits /internal/sso/consume, which sets the
    normal session cookies and lands on the dashboard (GitHub-OAuth pattern)."""
    _require_internal_key(request)
    db = get_db()
    user = await _require_user(payload.external_ref, payload.email)
    if user.get("is_active") is False:
        raise HTTPException(status_code=403, detail="Account suspended")

    target = payload.return_to if payload.return_to.startswith("/") else "/app"
    token = secrets.token_urlsafe(40)
    await db.internal_sso_tokens.insert_one({
        "id": str(uuid.uuid4()),
        "token": token,
        "user_id": user["id"],
        "return_to": target,
        "used": False,
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=SSO_TOKEN_TTL_SECONDS)).isoformat(),
        "created_at": _now_iso(),
    })
    audit_log(action="internal.sso_issue", actor=user, resource_type="user", resource_id=user["id"],
              meta={"external_ref": payload.external_ref}, request=request)
    return {
        "ok": True,
        "url": f"{_frontend_url()}/api/internal/sso/consume?token={token}",
        "expires_in": SSO_TOKEN_TTL_SECONDS,
    }


@router.get("/sso/consume")
async def consume_sso_link(token: str = ""):
    """Browser-facing (no internal key). Single-use, 120s validity."""
    db = get_db()
    frontend = _frontend_url()
    doc = await db.internal_sso_tokens.find_one_and_update(
        {"token": token, "used": False},
        {"$set": {"used": True, "used_at": _now_iso()}},
    )
    if not doc or doc.get("expires_at", "") < _now_iso():
        return RedirectResponse(url=f"{frontend}/login?error=sso_expired", status_code=302)
    user = await db.users.find_one({"id": doc["user_id"]}, {"_id": 0, "password_hash": 0})
    if not user or user.get("is_active") is False:
        return RedirectResponse(url=f"{frontend}/login?error=sso_invalid", status_code=302)

    response = RedirectResponse(url=f"{frontend}{doc.get('return_to') or '/app'}", status_code=302)
    access = create_access_token(user["id"], user["email"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    audit_log(action="internal.sso_consume", actor=user, resource_type="user", resource_id=user["id"])
    return response
