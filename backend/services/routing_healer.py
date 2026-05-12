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
    """Test if Traefik has a HEALTHY route for this FQDN. Returns one of:
      {"routed": True}                            → real app responding 2xx/3xx
      {"routed": False, "reason": "default_cert"} → Traefik serves default cert
      {"routed": False, "reason": "no_route"}     → 404 with Traefik fingerprint
      {"routed": False, "reason": "backend_down"} → 502/503/504 (route exists,
                                                    container is gone/crashed)
      {"routed": False, "reason": "unreachable"}  → connection failed
    """
    # 1) Direct TLS handshake on port 443 — read the cert subject WITHOUT
    #    httpx internals. If the server presents the Traefik default cert,
    #    Traefik has no router matching this hostname → ALWAYS broken.
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(fqdn, 443, ssl=ctx, server_hostname=fqdn),
            timeout=6.0,
        )
        peer_cert = writer.get_extra_info("peercert") or {}
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        subj = dict(x[0] for x in peer_cert.get("subject", []))
        cn = subj.get("commonName", "")
        if cn == TRAEFIK_DEFAULT_CERT_CN:
            return {"routed": False, "reason": "default_cert", "cert_cn": cn}
    except (asyncio.TimeoutError, OSError, ssl.SSLError):
        # TLS handshake failed entirely → fall through to HTTP probe to
        # diagnose further (port 80 may still tell us what's wrong).
        pass

    # 2) HTTP probe — Traefik default 404 has a precise fingerprint.
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=False) as cli:
            r = await cli.get(f"http://{fqdn}/")
            body = r.content or b""
            if r.status_code in (502, 503, 504):
                return {"routed": False, "reason": "backend_down", "status": r.status_code}
            if r.status_code == 404 and TRAEFIK_NO_ROUTE_BODY in body:
                return {"routed": False, "reason": "no_route", "status": 404}
            if r.status_code in (200, 301, 302, 307, 308):
                return {"routed": True, "status": r.status_code}
    except httpx.HTTPError as e:
        # 3) HTTP failed → try HTTPS one more time as a fallback (cert may
        #    still be default, that's ok — we just need to see the status).
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            async with httpx.AsyncClient(verify=ctx, timeout=6.0, follow_redirects=False) as cli:
                r = await cli.get(f"https://{fqdn}/")
                if r.status_code in (502, 503, 504):
                    return {"routed": False, "reason": "backend_down", "status": r.status_code}
                if r.status_code in (200, 301, 302, 307, 308):
                    return {"routed": True, "status": r.status_code}
        except httpx.HTTPError:
            return {"routed": False, "reason": "unreachable", "error": str(e)[:160]}
        return {"routed": False, "reason": "unreachable", "error": str(e)[:160]}

    # 4) Anything else we got an HTTP response for but can't classify → treat
    #    as broken so the healer at least gives it a shot.
    return {"routed": False, "reason": "no_route", "status": getattr(r, "status_code", None)}


async def _push_fqdn_and_restart(app: dict) -> dict:
    """Re-push the FQDN to Coolify and FORCE-REDEPLOY so the Traefik labels
    actually regenerate. Returns a structured report. Idempotent.

    Coolify v4 background (gotcha that caused the entire bug):
      * The PATCH field is `domains` (NOT `fqdn`).
      * Even after a successful PATCH, Coolify does NOT auto-regenerate the
        container's custom_labels — restart alone leaves Traefik with the OLD
        labels. ONLY a fresh deploy(force=true) regenerates labels from the
        new fqdn and writes them onto the new container.
      * See: github.com/coollabsio/coolify/issues/6281
    """
    fqdn = app.get("cloudflare_fqdn")
    coolify_uuid = app.get("coolify_app_uuid")
    if not fqdn or not coolify_uuid:
        return {"action": "noop", "reason": "missing fqdn or coolify uuid"}
    desired = f"https://{fqdn}"
    # 1) PATCH `domains` on the application (the Coolify v4 way).
    try:
        await coolify.set_domains(coolify_uuid, desired)
    except Exception as e:
        return {"action": "patch_failed", "error": str(e)[:200]}
    # 2) Verify the patch landed.
    info = await coolify.get_application(coolify_uuid)
    if not info:
        return {"action": "verify_failed", "reason": "app gone on build engine"}
    landed = (info.get("fqdn") or info.get("domains") or "").split(",")[0].strip()
    if landed and (landed != desired and fqdn not in landed):
        logger.warning(
            "routing-healer: Coolify did not accept domains for %s (wanted=%s got=%s)",
            app.get("id"), desired, landed,
        )
    # 3) FORCE REDEPLOY — this is the step that ACTUALLY fixes routing. A
    #    restart only bounces the container with the OLD labels; a force
    #    redeploy makes Coolify regenerate the docker labels from the new
    #    domains and ship them with a fresh container.
    try:
        res = await coolify.deploy(coolify_uuid, force=True)
    except Exception as e:
        return {"action": "deploy_failed", "error": str(e)[:200], "landed_fqdn": landed}
    deploy_uuid = (res or {}).get("deployment_uuid") or (res or {}).get("uuid")
    return {
        "action": "healed",
        "landed_fqdn": landed or desired,
        "deployment_uuid": deploy_uuid,
        "note": "Forced redeploy — Traefik labels will be regenerated. SSL cert issuance can take 30-60s after the container is up.",
    }


async def heal_app(app_id: str) -> dict:
    """Public entrypoint — heal a single app's routing. Used by the admin
    "Heal" button and by the background healer.

    Returns immediately after triggering the force-redeploy. The actual route
    becomes live 30-90s later when the new container is up + Traefik picks up
    the regenerated labels + Let's Encrypt issues the cert. The widget's 15s
    poll loop will reflect the change automatically.
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
        return {"ok": True, "already_healthy": True, "fqdn": fqdn, "before": probe}
    report = await _push_fqdn_and_restart(app)
    await db.apps.update_one(
        {"id": app_id},
        {"$set": {
            "routing_last_probe": _now(),
            "routing_last_probe_reason": probe.get("reason"),
            "routing_last_heal_action": report.get("action"),
            "routing_last_heal_at": _now(),
        }},
    )
    return {
        "ok": report.get("action") == "healed",
        "fqdn": fqdn,
        "before": probe,
        "action": report,
        "eta_seconds": 60,
        "message": "Force-redeploy triggered. Traefik routes + SSL cert will be live in 30-90s.",
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
