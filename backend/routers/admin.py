"""Platform-admin routes.

Everything here requires user.role == 'admin'. Exposes:
  * GET  /admin/integrations       → health snapshot of Coolify, Mollie, GitHub OAuth, VIES
  * GET  /admin/platform-settings  → current Cloudflare + root-domain config (token is redacted)
  * PUT  /admin/platform-settings  → update Cloudflare token + root domain; encrypted at rest
  * POST /admin/vat/test           → wraps services.vat.validate_vies for the admin UI
  * GET  /admin/users              → list DeployHub users (for future user-management)
"""
import asyncio
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from db import get_db
from auth_utils import get_current_user
from crypto_utils import encrypt_token, decrypt_token
from clients.coolify import coolify
from clients.mollie import mollie
from services.vat import validate_vies, EU_VAT_RATES, home_country
from services.plans import (
    list_plans as plans_list,
    get_plan as plans_get,
    update_plan as plans_update,
    workspace_usage,
)
from services.grandfathering import apply_price_change, DEFAULT_NOTICE_DAYS

router = APIRouter(tags=["admin"])
logger = logging.getLogger(__name__)


async def _require_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    return user


PLATFORM_SETTINGS_ID = "platform-singleton"


async def get_platform_settings() -> dict:
    """Return the single platform_settings doc, or an empty default. Raw —
    includes the encrypted Cloudflare token."""
    db = get_db()
    doc = await db.platform_settings.find_one({"id": PLATFORM_SETTINGS_ID}, {"_id": 0}) or {}
    return doc


def _redact_settings(doc: dict) -> dict:
    """Redact secrets before handing the doc to the frontend."""
    out = dict(doc)
    # Never leak the encrypted token — just tell the UI whether one is configured.
    out["cloudflare_api_token_set"] = bool(out.pop("cloudflare_api_token_enc", None))
    out.pop("_id", None)
    return out


@router.get("/admin/integrations")
async def integrations(request: Request):
    await _require_admin(request)
    # Ping each integration with aggressive timeouts so the admin page isn't blocked
    # if any one of them is down.
    cool = {
        "configured": coolify.configured,
        "base_url": coolify.base,
    }
    if coolify.configured:
        try:
            cool["health"] = await asyncio.wait_for(coolify.health(), timeout=3.5)
        except Exception as e:
            cool["health"] = {"ok": False, "error": str(e)[:120] or "timeout"}
    moll = {
        "configured": mollie.configured,
        "mode": "live" if (mollie.api_key or "").startswith("live_") else ("test" if (mollie.api_key or "").startswith("test_") else None),
    }
    gh = {
        "client_id": os.environ.get("GITHUB_CLIENT_ID") or os.environ.get("GITHUB_OAUTH_CLIENT_ID") or None,
        "callback_url": os.environ.get("GITHUB_OAUTH_REDIRECT_URI") or None,
        "configured": bool(
            (os.environ.get("GITHUB_CLIENT_ID") or os.environ.get("GITHUB_OAUTH_CLIENT_ID"))
            and (os.environ.get("GITHUB_CLIENT_SECRET") or os.environ.get("GITHUB_OAUTH_CLIENT_SECRET"))
        ),
    }
    return {
        "coolify": cool,
        "mollie": moll,
        "github_oauth": gh,
        "company_country": home_country(),
        "eu_vat_countries": len(EU_VAT_RATES),
    }


@router.get("/admin/platform-settings")
async def read_platform_settings(request: Request):
    await _require_admin(request)
    doc = await get_platform_settings()
    return _redact_settings(doc)


class PlatformSettingsUpdate(BaseModel):
    cloudflare_api_token: str | None = None   # plaintext from the form; "" → clear
    cloudflare_zone_id: str | None = None
    cloudflare_zone_name: str | None = None   # root domain, e.g. "deployhub.app"
    default_subdomain_target_ip: str | None = None  # A-record target (Coolify server IP)
    default_subdomain_target_host: str | None = None  # optional CNAME target
    company_country: str | None = None
    invoice_series_prefix: str | None = None  # e.g. "2026"


@router.put("/admin/platform-settings")
async def update_platform_settings(payload: PlatformSettingsUpdate, request: Request):
    await _require_admin(request)
    db = get_db()
    current = await get_platform_settings()
    data = payload.model_dump(exclude_unset=True)

    # Handle Cloudflare token: encrypt + persist; "" means "clear".
    if "cloudflare_api_token" in data:
        tok = (data.pop("cloudflare_api_token") or "").strip()
        if tok:
            current["cloudflare_api_token_enc"] = encrypt_token(tok)
        else:
            current.pop("cloudflare_api_token_enc", None)

    for k, v in data.items():
        if v is None or v == "":
            current.pop(k, None)
        else:
            current[k] = v

    current["id"] = PLATFORM_SETTINGS_ID
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.platform_settings.update_one(
        {"id": PLATFORM_SETTINGS_ID}, {"$set": current}, upsert=True
    )
    # Refetch + redact
    return _redact_settings(await get_platform_settings())


class VatTestIn(BaseModel):
    vat_id: str


@router.post("/admin/vat/test")
async def test_vat(payload: VatTestIn, request: Request):
    await _require_admin(request)
    return await validate_vies(payload.vat_id)


@router.get("/admin/users")
async def list_users(request: Request):
    await _require_admin(request)
    db = get_db()
    users = await db.users.find({}, {"_id": 0, "password_hash": 0, "github_access_token": 0}).to_list(500)
    # Annotate with # of owned workspaces + github linked flag
    for u in users:
        u["workspaces_owned"] = await db.workspaces.count_documents({"owner_id": u["id"]})
    return users


@router.get("/admin/plans")
async def admin_list_plans(request: Request):
    """Returns every plan, including inactive ones, so admins can re-enable
    them. Pricing page uses /billing/plans (active-only)."""
    await _require_admin(request)
    return await plans_list(only_active=False)


class PlanUpdate(BaseModel):
    name: str | None = None
    price: float | None = None
    interval: str | None = None
    tagline: str | None = None
    features: list[str] | None = None
    limits: dict | None = None
    credits: int | None = None
    highlight: bool | None = None
    order: int | None = None
    active: bool | None = None
    fleet_view: bool | None = None
    support_sla_hours: int | None = None
    notice_days: int | None = None   # grandfather window if price increases


@router.put("/admin/plans/{plan_id}")
async def admin_update_plan(plan_id: str, payload: PlanUpdate, request: Request):
    await _require_admin(request)
    updates = payload.model_dump(exclude_unset=True)
    notice_days = updates.pop("notice_days", DEFAULT_NOTICE_DAYS)
    if not updates:
        raise HTTPException(status_code=400, detail="nothing to update")
    # If the price is changing UP, lock existing subscribers to the old price
    # for `notice_days` (default 180 ≈ 6 months) so customers aren't surprised.
    current = await plans_get(plan_id)
    if not current:
        raise HTTPException(status_code=404, detail="plan not found")
    affected = 0
    if "price" in updates:
        old_price = float(current.get("price") or 0)
        new_price = float(updates["price"])
        if new_price > old_price:
            affected = await apply_price_change(plan_id, old_price, new_price, notice_days=notice_days)
    plan = await plans_update(plan_id, updates)
    return {**(plan or {}), "grandfathered_subs": affected}


@router.get("/admin/plans/{plan_id}/usage")
async def admin_plan_usage(plan_id: str, request: Request):
    """Aggregate how many workspaces are on this plan (handy for pricing
    decisions: 'will this price change affect anyone?')."""
    await _require_admin(request)
    db = get_db()
    workspaces_on_plan = await db.workspaces.count_documents({"plan": plan_id})
    return {"plan_id": plan_id, "workspaces": workspaces_on_plan}


class PromoteIn(BaseModel):
    user_id: str
    role: str  # "admin" | "user"


@router.post("/admin/users/role")
async def set_user_role(payload: PromoteIn, request: Request):
    await _require_admin(request)
    if payload.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="invalid role")
    db = get_db()
    res = await db.users.update_one({"id": payload.user_id}, {"$set": {"role": payload.role}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="user not found")
    return {"ok": True, "role": payload.role}


async def get_cloudflare_config() -> dict | None:
    """Decrypt Cloudflare config for internal use (e.g. DNS automation).
    Returns {token, zone_id, zone_name, target_ip, target_host} or None if
    not fully configured."""
    doc = await get_platform_settings()
    enc = doc.get("cloudflare_api_token_enc")
    zone_id = doc.get("cloudflare_zone_id")
    zone_name = doc.get("cloudflare_zone_name")
    if not (enc and zone_id and zone_name):
        return None
    try:
        token = decrypt_token(enc)
    except Exception:
        return None
    return {
        "token": token,
        "zone_id": zone_id,
        "zone_name": zone_name,
        "target_ip": doc.get("default_subdomain_target_ip"),
        "target_host": doc.get("default_subdomain_target_host"),
    }
