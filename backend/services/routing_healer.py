"""Self-healing for Cloudflare → Coolify → Traefik routing.

Permanent fix for the "no available server" + "TRAEFIK DEFAULT CERT" symptom:
DNS resolves, port 80/443 are open, but Traefik has no route registered for
the app's FQDN. Symptom matrix:

  - DNS missing                   → not our problem (admin must configure CF)
  - DNS OK, no Coolify app        → orphan pool record → cleanup
  - DNS OK, app exists, FQDN
    not registered in Coolify     → re-push FQDN to Coolify
  - DNS OK, FQDN in Coolify,
    container stopped             → restart container
  - DNS OK, FQDN in Coolify,
    container running, Traefik
    serves default cert           → labels stale → restart container so
                                     Traefik re-reads docker labels

Detection signature: HTTPS request returns the Traefik default self-signed
certificate (CN=TRAEFIK DEFAULT CERT) instead of a Let's Encrypt cert. Also
treats sustained HTTP 404 from Traefik (with that exact body) as "no route".
"""
from __future__ import annotations

import asyncio
import logging
import ssl
from datetime import datetime, timezone
from typing import Optional

import httpx

from clients.coolify import coolify
from clients.cloudflare import delete_dns_record
from db import get_db

logger = logging.getLogger(__name__)

TRAEFIK_DEFAULT_CERT_CN = "TRAEFIK DEFAULT CERT"
# Body Traefik returns when it has no route for the hostname.
TRAEFIK_NO_ROUTE_BODY = b"404 page not found"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _probe_traefik_route(fqdn: str) -> dict:
    """Test if Traefik has a route for this FQDN. Returns one of:
      {"routed": True}                            → real app responding
      {"routed": False, "reason": "default_cert"} → Traefik serves default cert
      {"routed": False, "reason": "no_route"}     → 404 with Traefik fingerprint
      {"routed": False, "reason": "unreachable"}  → connection failed
    """
    url_https = f"https://{fqdn}/"
    url_http = f"http://{fqdn}/"
    # 1) Try HTTPS first and capture the cert subject. We use a context that
    #    accepts self-signed so we can SEE the Traefik default cert.
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        async with httpx.AsyncClient(verify=ctx, timeout=6.0, follow_redirects=False) as cli:
            r = await cli.get(url_https)
            # Grab the peer cert subject through the underlying transport.
            try:
                peer = r.extensions.get("network_stream").get_extra_info("ssl_object")
                if peer:
                    subj = dict(x[0] for x in peer.getpeercert().get("subject", []))
                    cn = subj.get("commonName", "")
                    if cn == TRAEFIK_DEFAULT_CERT_CN:
                        return {"routed": False, "reason": "default_cert"}
            except Exception:
                pass  # fall through to body check
            # If we get a Let's Encrypt cert AND a non-404 response, app is routed
            if r.status_code == 404 and TRAEFIK_NO_ROUTE_BODY in (r.content or b""):
                return {"routed": False, "reason": "no_route"}
            return {"routed": True}
    except httpx.HTTPError:
        pass
    # 2) HTTPS failed entirely — try plain HTTP to see if Traefik is up at all.
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=False) as cli:
            r = await cli.get(url_http)
            if r.status_code == 404 and TRAEFIK_NO_ROUTE_BODY in (r.content or b""):
                return {"routed": False, "reason": "no_route"}
            # Any redirect to HTTPS or 200 means there's *some* route
            if r.status_code in (301, 302, 308, 200):
                return {"routed": True}
            return {"routed": False, "reason": "no_route"}
    except httpx.HTTPError:
        return {"routed": False, "reason": "unreachable"}


async def _push_fqdn_and_restart(app: dict) -> dict:
    """Re-push the FQDN to Coolify and restart the container. Returns a
    structured report. Idempotent."""
    fqdn = app.get("cloudflare_fqdn")
    coolify_uuid = app.get("coolify_app_uuid")
    if not fqdn or not coolify_uuid:
        return {"action": "noop", "reason": "missing fqdn or coolify uuid"}
    desired = f"https://{fqdn}"
    # 1) PATCH the FQDN on the application.
    try:
        await coolify.update_application(coolify_uuid, {"fqdn": desired})
    except Exception as e:
        return {"action": "patch_failed", "error": str(e)[:200]}
    # 2) Verify the patch landed.
    info = await coolify.get_application(coolify_uuid)
    if not info:
        return {"action": "verify_failed", "reason": "app gone on build engine"}
    landed = (info.get("fqdn") or "").split(",")[0].strip()
    if landed != desired and fqdn not in landed:
        # Coolify silently ignored the PATCH — log it but continue with restart.
        logger.warning(
            "routing-healer: Coolify did not accept fqdn for %s (wanted=%s got=%s)",
            app.get("id"), desired, landed,
        )
    # 3) Restart the container so Traefik re-reads the docker labels. This
    #    is the step that ACTUALLY fixes the "no route" symptom — a simple
    #    PATCH doesn't relabel a running container.
    try:
        await coolify.restart(coolify_uuid)
    except Exception as e:
        return {"action": "restart_failed", "error": str(e)[:200], "landed_fqdn": landed}
    return {"action": "healed", "landed_fqdn": landed or desired}


async def heal_app(app_id: str) -> dict:
    """Public entrypoint — heal a single app's routing. Used by the admin
    "Heal" button and by the background healer.
    """
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        return {"ok": False, "error": "app not found"}
    fqdn = app.get("cloudflare_fqdn")
    if not fqdn:
        return {"ok": False, "error": "app has no Cloudflare FQDN"}
    probe = await _probe_traefik_route(fqdn)
    if probe.get("routed"):
        return {"ok": True, "already_healthy": True, "fqdn": fqdn}
    report = await _push_fqdn_and_restart(app)
    # Re-probe briefly after restart (Traefik picks up new labels in ~3-5s)
    await asyncio.sleep(6)
    after = await _probe_traefik_route(fqdn)
    healed_at = _now() if after.get("routed") else None
    await db.apps.update_one(
        {"id": app_id},
        {"$set": {
            "routing_last_probe": _now(),
            "routing_last_probe_reason": probe.get("reason"),
            "routing_last_heal_action": report.get("action"),
            "routing_last_heal_at": _now(),
            "routing_last_healed_at": healed_at,
        }},
    )
    return {
        "ok": after.get("routed", False),
        "fqdn": fqdn,
        "before": probe,
        "action": report,
        "after": after,
    }


async def cleanup_orphan_pool_entries() -> dict:
    """Find pool entries marked `claimed` whose `app_id` either no longer
    exists or whose app has been deleted. Release the Cloudflare record and
    drop the pool row. Returns counts.
    """
    db = get_db()
    # Lazy imports to avoid circular references at module load.
    from routers.admin import get_cloudflare_config
    cfg = await get_cloudflare_config()
    if not cfg:
        return {"checked": 0, "released": 0, "skipped": "cloudflare not configured"}
    cur = db.cloudflare_subdomain_pool.find(
        {"status": "claimed", "app_id": {"$ne": None}},
        {"_id": 0, "id": 1, "record_id": 1, "fqdn": 1, "app_id": 1},
    )
    checked = 0
    released = 0
    async for entry in cur:
        checked += 1
        app = await db.apps.find_one({"id": entry["app_id"]}, {"_id": 0, "id": 1})
        if app:
            continue  # still in use
        # Orphan — delete CF record then drop pool row.
        try:
            ok = await delete_dns_record(token=cfg["token"], zone_id=cfg["zone_id"], record_id=entry["record_id"])
        except Exception as e:
            logger.warning("orphan cleanup: CF delete failed for %s: %s", entry["fqdn"], e)
            ok = False
        if ok:
            await db.cloudflare_subdomain_pool.delete_one({"record_id": entry["record_id"]})
            released += 1
            logger.info("orphan cleanup: released %s (app %s gone)", entry["fqdn"], entry["app_id"])
    return {"checked": checked, "released": released}


async def routing_healer_tick() -> dict:
    """Scheduled job — walk all live apps with a Cloudflare FQDN, probe Traefik,
    auto-heal anything broken. Capped at 25 apps per tick so a global outage
    doesn't lock up the scheduler.
    """
    db = get_db()
    # Cleanup orphan pool records first (cheap, no app to heal).
    orphans = await cleanup_orphan_pool_entries()
    apps = await db.apps.find(
        {
            "status": "live",
            "cloudflare_fqdn": {"$ne": None, "$exists": True},
            "coolify_app_uuid": {"$ne": None, "$exists": True},
        },
        {"_id": 0, "id": 1, "cloudflare_fqdn": 1, "coolify_app_uuid": 1, "routing_last_heal_action": 1, "routing_last_heal_at": 1, "routing_heal_attempts": 1},
    ).limit(25).to_list(25)
    if not apps:
        return {"checked": 0, "healed": 0, "orphans": orphans}
    healed = 0
    # Probe in parallel, heal sequentially to avoid Coolify rate-limits.
    probes = await asyncio.gather(*[_probe_traefik_route(a["cloudflare_fqdn"]) for a in apps], return_exceptions=True)
    for app, probe in zip(apps, probes):
        if isinstance(probe, Exception):
            continue
        if probe.get("routed"):
            continue
        # Cap retries per app at 3 in any 1h window so we don't restart loops.
        attempts = int(app.get("routing_heal_attempts") or 0)
        if attempts >= 3:
            last = app.get("routing_last_heal_at")
            if last:
                try:
                    last_dt = datetime.fromisoformat(last)
                    if (datetime.now(timezone.utc) - last_dt).total_seconds() < 3600:
                        continue
                except Exception:
                    pass
            # Reset the counter after the 1h cooldown so we try again later.
            attempts = 0
        logger.info("routing-healer: app=%s fqdn=%s reason=%s — healing (attempt %d)",
                    app["id"], app["cloudflare_fqdn"], probe.get("reason"), attempts + 1)
        report = await _push_fqdn_and_restart(app)
        await db.apps.update_one(
            {"id": app["id"]},
            {
                "$set": {
                    "routing_last_probe": _now(),
                    "routing_last_probe_reason": probe.get("reason"),
                    "routing_last_heal_action": report.get("action"),
                    "routing_last_heal_at": _now(),
                },
                "$inc": {"routing_heal_attempts": 1},
            },
        )
        if report.get("action") == "healed":
            healed += 1
    return {"checked": len(apps), "healed": healed, "orphans": orphans}
