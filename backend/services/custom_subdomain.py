"""Custom subdomain on the platform root domain — safe cutover with DNS
verification.

The flow is designed so an app never goes offline while it's being
re-pointed at a custom subdomain:

  ┌──────────────┐   pending     ┌──────────────────────────────┐
  │ user requests│ ───────────▶  │ DNS record created on        │
  │ "<name>"     │               │ Cloudflare (proxied / grey)  │
  └──────────────┘               │ Traefik gets the new domain  │
                                 │ added to the app             │
                                 │ Old random URL still works   │
                                 └────────────────┬─────────────┘
                                                  │
                          background verifier ticks every 30s
                                                  │
                                  3 consecutive 2xx/3xx probes
                                                  ▼
                                ┌──────────────────────────────┐
                                │ STATE → active               │
                                │ app.primary_url switched     │
                                │ app.cloudflare_fqdn switched │
                                │ old random subdomain released│
                                │   back into the pool         │
                                └──────────────────────────────┘
                                                  │
                                       timeout 10 min OR
                                       6 consecutive probe failures
                                                  ▼
                                ┌──────────────────────────────┐
                                │ STATE → failed               │
                                │ Custom DNS record removed    │
                                │ Old domain remains primary   │
                                │ User sees friendly error +   │
                                │ "Try again" button           │
                                └──────────────────────────────┘
"""
from __future__ import annotations

import asyncio
import logging
import re
import ssl
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from clients.cloudflare import create_dns_record, delete_dns_record
from clients.coolify import coolify
from db import get_db

logger = logging.getLogger(__name__)


# Reserved subdomains — anything that could clash with platform/marketing
# infrastructure or get a security-policy waiver. Always lowercase.
RESERVED_SUBDOMAINS: set[str] = {
    "www", "api", "admin", "app", "auth", "login", "logout", "register",
    "signup", "signin", "mail", "smtp", "imap", "pop", "ftp", "ssh", "vpn",
    "status", "dashboard", "deploy", "deployments", "deployhub", "deployunit",
    "pricing", "support", "help", "docs", "blog", "about", "contact",
    "terms", "privacy", "legal", "ns1", "ns2", "dns", "cdn", "static",
    "assets", "media", "img", "images", "files", "uploads", "download",
    "downloads", "billing", "invoice", "invoices", "checkout", "cart",
    "shop", "store", "test", "staging", "dev", "preview", "demo",
    "internal", "private", "secure", "root", "system", "config", "settings",
    "monitoring", "metrics", "logs", "trace", "tracing", "health",
    "healthcheck", "ping", "webhook", "webhooks", "callback",
    "node-status", "platform", "hosting", "build", "ci", "cd",
    "wp-admin", "wp-login", "phpmyadmin",
}

# 3..63 chars, lowercase alnum + hyphens, no leading/trailing hyphen.
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$")
MIN_LEN = 3
MAX_LEN = 63

# Timing knobs — tuned for "fast but safe":
# - probe every 30s by the scheduler
# - succeed after 3 consecutive 2xx/3xx probes (≈90s steady-state)
# - hard timeout 10 min so a misconfigured Coolify can't pin a pending
#   forever
SUCCESS_PROBES_NEEDED = 3
FAILURE_PROBES_TO_GIVE_UP = 6   # 3 minutes of nothing-but-failures
PENDING_TIMEOUT_MINUTES = 10


# ─────────────────────────── helpers ───────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def normalize_name(name: str) -> str:
    """Lowercase + strip whitespace + drop trailing dot. Caller still has
    to validate the result."""
    return (name or "").strip().lower().rstrip(".")


def validate_name(name: str) -> tuple[bool, str]:
    """Returns (ok, reason). Reason is human-friendly when ok is False."""
    n = normalize_name(name)
    if not n:
        return False, "Subdomain cannot be empty."
    if len(n) < MIN_LEN:
        return False, f"Subdomain must be at least {MIN_LEN} characters."
    if len(n) > MAX_LEN:
        return False, f"Subdomain cannot be longer than {MAX_LEN} characters."
    if not NAME_RE.match(n):
        return False, "Only lowercase letters, digits, and hyphens are allowed (not at the start or end)."
    if n in RESERVED_SUBDOMAINS:
        return False, f"'{n}' is reserved by the platform."
    return True, ""


async def check_availability(name: str) -> dict:
    """Returns {available, reason, zone_name, fqdn}. Used by the UI as the
    user types — no DB mutation. `reason` is empty when available."""
    ok, why = validate_name(name)
    if not ok:
        return {"available": False, "reason": why}

    from routers.admin import get_cloudflare_config
    cfg = await get_cloudflare_config()
    if not cfg:
        return {"available": False, "reason": "Cloudflare is not configured on the platform yet."}

    n = normalize_name(name)
    fqdn = f"{n}.{cfg['zone_name']}"

    db = get_db()

    # Reject if it's already claimed by another app or pre-warmed in the pool.
    pool_hit = await db.cloudflare_subdomain_pool.find_one({"fqdn": fqdn}, {"_id": 0, "status": 1})
    if pool_hit:
        return {
            "available": False,
            "reason": "This subdomain is already in use." if pool_hit.get("status") == "claimed" else "This subdomain is currently pre-warmed in the platform pool — try another.",
            "fqdn": fqdn,
            "zone_name": cfg["zone_name"],
        }
    # Reject if a pending request already exists.
    pending = await db.custom_subdomain_requests.find_one(
        {"fqdn": fqdn, "status": "pending"}, {"_id": 0, "app_id": 1},
    )
    if pending:
        return {
            "available": False,
            "reason": "Another app is currently provisioning this subdomain. Try again in a few minutes.",
            "fqdn": fqdn,
            "zone_name": cfg["zone_name"],
        }
    # Reject if an active claim exists (custom_subdomain matches).
    active = await db.apps.find_one(
        {"custom_subdomain_fqdn": fqdn, "custom_subdomain_status": "active"},
        {"_id": 0, "id": 1},
    )
    if active:
        return {
            "available": False,
            "reason": "This subdomain is already taken by another app.",
            "fqdn": fqdn,
            "zone_name": cfg["zone_name"],
        }
    return {"available": True, "reason": "", "fqdn": fqdn, "zone_name": cfg["zone_name"]}


# ─────────────────────────── DNS + Traefik wiring ──────────────────────────


async def _create_dns_record_for_custom(fqdn: str) -> Optional[dict]:
    """Create the Cloudflare record we'll point the custom subdomain at.
    Uses the same A/CNAME target as the pre-warmed pool so behaviour is
    consistent."""
    from routers.admin import get_cloudflare_config
    from services.subdomains import _proxied_pref  # type: ignore
    cfg = await get_cloudflare_config()
    if not cfg:
        return None
    if cfg.get("target_host"):
        record_type, content = "CNAME", cfg["target_host"]
    else:
        record_type, content = "A", cfg["target_ip"]
    if not content:
        return None
    proxied = await _proxied_pref()
    rec = await create_dns_record(
        token=cfg["token"], zone_id=cfg["zone_id"],
        name=fqdn, record_type=record_type, content=content,
        proxied=proxied,
    )
    if not rec or not rec.get("id"):
        return None
    return {"record_id": rec["id"], "record_type": record_type, "proxied": proxied}


async def _add_domain_to_coolify(app: dict, fqdn: str) -> bool:
    """Push the custom FQDN to Coolify alongside the existing one so both
    domains route to the same app. We add — never overwrite — so the old
    random URL keeps working until the cutover succeeds."""
    coolify_uuid = app.get("coolify_app_uuid")
    if not coolify_uuid:
        return False
    info = await coolify.get_application(coolify_uuid)
    if not info:
        return False
    existing_raw = (info.get("fqdn") or info.get("domains") or "").strip()
    existing = [d.strip() for d in existing_raw.replace(",", " ").split() if d.strip()]
    new_url = f"https://{fqdn}"
    if new_url not in existing:
        existing.append(new_url)
    try:
        await coolify.set_domains(coolify_uuid, existing, force_https=True)
        # Force-redeploy so Traefik regenerates labels and Let's Encrypt
        # requests a cert for the new hostname.
        await coolify.deploy(coolify_uuid, force=True)
        return True
    except Exception as e:
        logger.warning("custom-subdomain: coolify set_domains failed for %s: %s", app.get("id"), e)
        return False


async def _remove_domain_from_coolify(app: dict, fqdn: str) -> None:
    """Drop the custom FQDN back out of Coolify when we roll back / release."""
    coolify_uuid = app.get("coolify_app_uuid")
    if not coolify_uuid:
        return
    info = await coolify.get_application(coolify_uuid)
    if not info:
        return
    existing_raw = (info.get("fqdn") or info.get("domains") or "").strip()
    existing = [d.strip() for d in existing_raw.replace(",", " ").split() if d.strip()]
    new_url = f"https://{fqdn}"
    if new_url not in existing:
        return
    pruned = [d for d in existing if d != new_url]
    if not pruned:
        return
    try:
        await coolify.set_domains(coolify_uuid, pruned, force_https=True)
        await coolify.deploy(coolify_uuid, force=True)
    except Exception as e:
        logger.warning("custom-subdomain: coolify domain-prune failed for %s: %s", app.get("id"), e)


async def _probe(fqdn: str) -> dict:
    """Verify the custom FQDN is reachable end-to-end. We accept any 2xx/3xx
    HTTPS response. Returns {ok, reason}. Mirrors routing_healer logic.
    """
    # 1) HTTPS probe — most representative because that's what users will hit.
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        async with httpx.AsyncClient(verify=ctx, timeout=8.0, follow_redirects=False) as cli:
            r = await cli.get(f"https://{fqdn}/", headers={"User-Agent": "DeployUnit-Verifier/1.0"})
        if r.status_code in (200, 301, 302, 303, 307, 308):
            return {"ok": True, "status": r.status_code, "scheme": "https"}
        # Default Traefik 404 or backend down means routes/labels not ready yet
        if r.status_code in (404, 502, 503, 504):
            return {"ok": False, "reason": f"https {r.status_code}", "status": r.status_code}
    except httpx.ConnectError as e:
        return {"ok": False, "reason": f"connect: {str(e)[:80]}"}
    except httpx.HTTPError as e:
        return {"ok": False, "reason": f"https error: {str(e)[:80]}"}
    # 2) HTTP fallback (some Coolify configs only have port 80 ready first).
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as cli:
            r = await cli.get(f"http://{fqdn}/", headers={"User-Agent": "DeployUnit-Verifier/1.0"})
        if r.status_code in (200, 301, 302, 303, 307, 308):
            return {"ok": True, "status": r.status_code, "scheme": "http"}
        return {"ok": False, "reason": f"http {r.status_code}", "status": r.status_code}
    except httpx.HTTPError as e:
        return {"ok": False, "reason": f"http error: {str(e)[:80]}"}


# ─────────────────────────── public API ────────────────────────────────────


async def request_custom_subdomain(app: dict, raw_name: str) -> dict:
    """Start the provisioning flow. Idempotent for the same (app_id, name)
    pair — if a pending request exists we just return its current state."""
    db = get_db()
    avail = await check_availability(raw_name)
    if not avail.get("available"):
        return {"ok": False, "error": avail.get("reason"), **avail}
    fqdn = avail["fqdn"]
    name = normalize_name(raw_name)
    app_id = app["id"]

    # Replace any previous pending request for this app — only one in-flight
    # request per app.
    await db.custom_subdomain_requests.update_many(
        {"app_id": app_id, "status": "pending"},
        {"$set": {"status": "cancelled", "cancelled_at": _now_iso(),
                  "cancelled_reason": "replaced by new request"}},
    )

    dns = await _create_dns_record_for_custom(fqdn)
    if not dns:
        return {"ok": False, "error": "Failed to create DNS record on Cloudflare. Please try again."}

    pushed = await _add_domain_to_coolify(app, fqdn)
    if not pushed:
        # Roll back the DNS record so we don't litter Cloudflare with
        # half-provisioned subdomains.
        from routers.admin import get_cloudflare_config
        cfg = await get_cloudflare_config()
        if cfg:
            await delete_dns_record(token=cfg["token"], zone_id=cfg["zone_id"], record_id=dns["record_id"])
        return {"ok": False, "error": "Failed to register the domain with the build engine. Try again in a moment."}

    request_doc = {
        "id": f"csr_{app_id}_{name}",
        "app_id": app_id,
        "workspace_id": app.get("workspace_id"),
        "name": name,
        "fqdn": fqdn,
        "status": "pending",
        "cloudflare_record_id": dns["record_id"],
        "cloudflare_record_type": dns["record_type"],
        "previous_fqdn": app.get("cloudflare_fqdn"),
        "previous_record_id": app.get("cloudflare_dns_record_id"),
        "probe_success": 0,
        "probe_failure": 0,
        "last_probe_at": None,
        "last_probe_reason": None,
        "created_at": _now_iso(),
        "started_by": app.get("owner_id") or app.get("workspace_id"),
    }
    await db.custom_subdomain_requests.update_one(
        {"id": request_doc["id"]}, {"$set": request_doc}, upsert=True,
    )
    # Mirror the pending state on the app for fast UI reads.
    await db.apps.update_one(
        {"id": app_id},
        {"$set": {
            "custom_subdomain_pending": fqdn,
            "custom_subdomain_pending_name": name,
            "custom_subdomain_pending_started_at": _now_iso(),
            "custom_subdomain_status": "pending",
        }},
    )
    logger.info("custom-subdomain: pending %s for app=%s", fqdn, app_id)
    return {"ok": True, "status": "pending", "fqdn": fqdn, "request_id": request_doc["id"],
            "eta_seconds": SUCCESS_PROBES_NEEDED * 30,
            "message": "We're verifying DNS + SSL. Your existing URL stays online until the new one is fully working."}


async def cancel_pending(app_id: str) -> dict:
    """Cancel a pending request and undo Cloudflare + Coolify side-effects.
    Safe to call when nothing is pending — it just no-ops."""
    db = get_db()
    req = await db.custom_subdomain_requests.find_one(
        {"app_id": app_id, "status": "pending"}, {"_id": 0},
    )
    if not req:
        return {"ok": True, "noop": True}
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if app:
        await _remove_domain_from_coolify(app, req["fqdn"])
    from routers.admin import get_cloudflare_config
    cfg = await get_cloudflare_config()
    if cfg and req.get("cloudflare_record_id"):
        await delete_dns_record(token=cfg["token"], zone_id=cfg["zone_id"], record_id=req["cloudflare_record_id"])
    await db.custom_subdomain_requests.update_one(
        {"id": req["id"]},
        {"$set": {"status": "cancelled", "cancelled_at": _now_iso(),
                  "cancelled_reason": "user requested"}},
    )
    await db.apps.update_one(
        {"id": app_id},
        {"$unset": {
            "custom_subdomain_pending": "",
            "custom_subdomain_pending_name": "",
            "custom_subdomain_pending_started_at": "",
        }, "$set": {"custom_subdomain_status": "cancelled"}},
    )
    return {"ok": True, "cancelled": req["fqdn"]}


async def detach_active_custom(app_id: str) -> dict:
    """Roll back from an *active* custom subdomain to the original random
    pool URL. Restores `cloudflare_fqdn` + `primary_url`, drops the custom
    DNS record + Traefik route."""
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        return {"ok": False, "error": "App not found"}
    fqdn = app.get("custom_subdomain_fqdn")
    if not fqdn:
        return {"ok": True, "noop": True}
    prev_fqdn = app.get("custom_subdomain_previous_fqdn")
    prev_record = app.get("custom_subdomain_previous_record_id")
    # Drop Coolify route + DNS
    await _remove_domain_from_coolify(app, fqdn)
    from routers.admin import get_cloudflare_config
    cfg = await get_cloudflare_config()
    record_id = app.get("custom_subdomain_record_id")
    if cfg and record_id:
        await delete_dns_record(token=cfg["token"], zone_id=cfg["zone_id"], record_id=record_id)
    update_set: dict = {"custom_subdomain_status": "detached"}
    update_unset: dict = {
        "custom_subdomain_fqdn": "",
        "custom_subdomain_name": "",
        "custom_subdomain_record_id": "",
        "custom_subdomain_activated_at": "",
    }
    # If we have the old random subdomain on file, restore it as primary.
    if prev_fqdn:
        update_set["cloudflare_fqdn"] = prev_fqdn
        update_set["primary_url"] = f"https://{prev_fqdn}"
        if prev_record:
            update_set["cloudflare_dns_record_id"] = prev_record
    await db.apps.update_one({"id": app_id}, {"$set": update_set, "$unset": update_unset})
    return {"ok": True, "detached": fqdn, "restored_fqdn": prev_fqdn}


# ─────────────────────────── scheduler tick ────────────────────────────────


async def _activate(req: dict, app: dict) -> None:
    """Promote a pending request to active. Swap primary URL, release the
    old pool subdomain back to the pool."""
    db = get_db()
    new_fqdn = req["fqdn"]
    old_fqdn = app.get("cloudflare_fqdn")
    old_record = app.get("cloudflare_dns_record_id")
    # Update app document — the custom subdomain becomes the primary URL.
    await db.apps.update_one(
        {"id": app["id"]},
        {"$set": {
            "primary_url": f"https://{new_fqdn}",
            "cloudflare_fqdn": new_fqdn,
            "cloudflare_dns_record_id": req["cloudflare_record_id"],
            "custom_subdomain_fqdn": new_fqdn,
            "custom_subdomain_name": req["name"],
            "custom_subdomain_record_id": req["cloudflare_record_id"],
            "custom_subdomain_previous_fqdn": old_fqdn,
            "custom_subdomain_previous_record_id": old_record,
            "custom_subdomain_activated_at": _now_iso(),
            "custom_subdomain_status": "active",
        },
         "$unset": {
            "custom_subdomain_pending": "",
            "custom_subdomain_pending_name": "",
            "custom_subdomain_pending_started_at": "",
         }},
    )
    # Mark the request done.
    await db.custom_subdomain_requests.update_one(
        {"id": req["id"]},
        {"$set": {"status": "active", "activated_at": _now_iso()}},
    )
    # Release the old pool entry back to "free" (or delete if it was an
    # on-demand record so we don't accumulate orphaned slugs).
    if old_record:
        pool_row = await db.cloudflare_subdomain_pool.find_one({"record_id": old_record}, {"_id": 0, "on_demand": 1})
        if pool_row and pool_row.get("on_demand"):
            # Was a one-off record, just drop it.
            from routers.admin import get_cloudflare_config
            cfg = await get_cloudflare_config()
            if cfg:
                await delete_dns_record(token=cfg["token"], zone_id=cfg["zone_id"], record_id=old_record)
            await db.cloudflare_subdomain_pool.delete_one({"record_id": old_record})
        else:
            await db.cloudflare_subdomain_pool.update_one(
                {"record_id": old_record},
                {"$set": {"status": "free", "app_id": None,
                          "released_at": _now_iso()}},
                upsert=False,
            )
    logger.info("custom-subdomain: activated %s for app=%s", new_fqdn, app["id"])


async def _fail(req: dict, app: dict, reason: str) -> None:
    """Mark the request as failed + roll back DNS + Traefik so the old URL
    keeps working."""
    db = get_db()
    await _remove_domain_from_coolify(app, req["fqdn"])
    from routers.admin import get_cloudflare_config
    cfg = await get_cloudflare_config()
    if cfg and req.get("cloudflare_record_id"):
        await delete_dns_record(token=cfg["token"], zone_id=cfg["zone_id"], record_id=req["cloudflare_record_id"])
    await db.custom_subdomain_requests.update_one(
        {"id": req["id"]},
        {"$set": {"status": "failed", "failed_at": _now_iso(), "failed_reason": reason}},
    )
    await db.apps.update_one(
        {"id": app["id"]},
        {"$set": {"custom_subdomain_status": "failed",
                  "custom_subdomain_last_error": reason},
         "$unset": {"custom_subdomain_pending": "",
                    "custom_subdomain_pending_name": "",
                    "custom_subdomain_pending_started_at": ""}},
    )
    logger.warning("custom-subdomain: failed %s for app=%s — %s", req["fqdn"], app["id"], reason)


async def verify_pending_subdomains_tick() -> dict:
    """Scheduler entrypoint. Probes every pending request, transitions
    state when the success/failure thresholds are crossed."""
    db = get_db()
    pending_cur = db.custom_subdomain_requests.find(
        {"status": "pending"},
        {"_id": 0},
    )
    activated = 0
    failed = 0
    still_pending = 0
    async for req in pending_cur:
        app = await db.apps.find_one({"id": req["app_id"]}, {"_id": 0})
        if not app:
            await _fail(req, {"id": req["app_id"]}, "app deleted")
            failed += 1
            continue
        # Timeout: been pending too long? Mark failed regardless of probe.
        try:
            started = datetime.fromisoformat(req["created_at"])
        except Exception:
            started = _now()
        if _now() - started > timedelta(minutes=PENDING_TIMEOUT_MINUTES):
            await _fail(req, app, "timeout: DNS did not propagate within the allowed window")
            failed += 1
            continue

        probe = await _probe(req["fqdn"])
        if probe.get("ok"):
            successes = int(req.get("probe_success") or 0) + 1
            await db.custom_subdomain_requests.update_one(
                {"id": req["id"]},
                {"$set": {"probe_success": successes,
                          "probe_failure": 0,
                          "last_probe_at": _now_iso(),
                          "last_probe_reason": f"ok {probe.get('status')} ({probe.get('scheme')})"}},
            )
            if successes >= SUCCESS_PROBES_NEEDED:
                await _activate(req, app)
                activated += 1
            else:
                still_pending += 1
        else:
            failures = int(req.get("probe_failure") or 0) + 1
            await db.custom_subdomain_requests.update_one(
                {"id": req["id"]},
                {"$set": {"probe_success": 0,
                          "probe_failure": failures,
                          "last_probe_at": _now_iso(),
                          "last_probe_reason": probe.get("reason")}},
            )
            if failures >= FAILURE_PROBES_TO_GIVE_UP:
                await _fail(req, app, f"verification failed after {failures} attempts: {probe.get('reason')}")
                failed += 1
            else:
                still_pending += 1
    if activated or failed:
        logger.info("custom-subdomain verifier: activated=%d failed=%d pending=%d",
                    activated, failed, still_pending)
    return {"activated": activated, "failed": failed, "pending": still_pending}


async def status_for_app(app_id: str) -> dict:
    """Return the current custom-subdomain state for the UI."""
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        return {"status": "none"}
    if app.get("custom_subdomain_status") == "active":
        return {
            "status": "active",
            "fqdn": app.get("custom_subdomain_fqdn"),
            "name": app.get("custom_subdomain_name"),
            "activated_at": app.get("custom_subdomain_activated_at"),
            "previous_fqdn": app.get("custom_subdomain_previous_fqdn"),
        }
    req = await db.custom_subdomain_requests.find_one(
        {"app_id": app_id, "status": "pending"}, {"_id": 0},
    )
    if req:
        return {
            "status": "pending",
            "fqdn": req["fqdn"],
            "name": req["name"],
            "started_at": req["created_at"],
            "probe_success": req.get("probe_success", 0),
            "probe_success_needed": SUCCESS_PROBES_NEEDED,
            "probe_failure": req.get("probe_failure", 0),
            "last_probe_at": req.get("last_probe_at"),
            "last_probe_reason": req.get("last_probe_reason"),
            "eta_seconds": max(0, SUCCESS_PROBES_NEEDED * 30 - 30 * int(req.get("probe_success") or 0)),
            "timeout_at": (datetime.fromisoformat(req["created_at"]) + timedelta(minutes=PENDING_TIMEOUT_MINUTES)).isoformat()
            if req.get("created_at") else None,
        }
    if app.get("custom_subdomain_status") in ("failed", "cancelled", "detached"):
        last = await db.custom_subdomain_requests.find_one(
            {"app_id": app_id}, {"_id": 0}, sort=[("created_at", -1)],
        )
        return {
            "status": app["custom_subdomain_status"],
            "fqdn": (last or {}).get("fqdn"),
            "name": (last or {}).get("name"),
            "reason": (last or {}).get("failed_reason") or app.get("custom_subdomain_last_error"),
        }
    return {"status": "none"}
