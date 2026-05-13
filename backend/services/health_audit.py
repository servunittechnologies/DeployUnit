"""Daily health audit — SSL certificate validity + domain registration
expiry checks for every custom domain on the platform.

Two distinct signals:
  * `ssl_invalid`    — HTTPS handshake fails / cert is expired / wrong CN
  * `domain_expiring`— registrar tells us the domain itself expires soon

We probe SSL ourselves (it's cheap, no external API needed). For registrar
expiry we rely on the `expires_at` field that the domains router writes
when WHOIS data is available — if it's not populated we just skip that
check rather than spawning an extra WHOIS request per tick.

Runs once every 6 hours from the APScheduler. The dispatcher's
per-event cooldown stops the same domain from pinging twice in 24h.
"""
from __future__ import annotations

import asyncio
import logging
import socket
import ssl
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import get_db
from services.event_dispatcher import dispatch_event

logger = logging.getLogger(__name__)


# Warn this many days before the domain registration expires.
DOMAIN_EXPIRY_WARNING_DAYS = 14
# Warn this many days before the SSL cert expires (Let's Encrypt rotates
# at 30 days remaining, so 7 is a safe "something is wrong" threshold).
SSL_EXPIRY_WARNING_DAYS = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _probe_ssl(hostname: str) -> dict:
    """TLS handshake → read peer cert. Returns one of:
      {"ok": True, "expires_at": datetime, "issuer": str}
      {"ok": False, "reason": "expired"|"handshake"|"wrong_host"|"unreachable", "detail": str}
    """
    loop = asyncio.get_running_loop()
    def _sync_probe():
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                return ssock.getpeercert()
    try:
        cert = await loop.run_in_executor(None, _sync_probe)
    except ssl.SSLCertVerificationError as e:
        # `verify failed: certificate has expired` is the most common
        # variant of this — but we treat any verify failure as invalid.
        return {"ok": False, "reason": "invalid", "detail": str(e)[:200]}
    except (socket.gaierror, socket.timeout, OSError) as e:
        return {"ok": False, "reason": "unreachable", "detail": str(e)[:200]}
    if not cert:
        return {"ok": False, "reason": "no_cert", "detail": "empty peer cert"}
    not_after = cert.get("notAfter")
    expires_at: Optional[datetime] = None
    if not_after:
        try:
            # OpenSSL prints "Jan 12 14:08:00 2026 GMT"
            expires_at = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            expires_at = None
    if expires_at and expires_at <= _now():
        return {"ok": False, "reason": "expired", "expires_at": expires_at.isoformat()}
    issuer = ""
    try:
        issuer_parts = cert.get("issuer") or ()
        for rdn in issuer_parts:
            for k, v in rdn:
                if k == "organizationName":
                    issuer = v
                    break
    except Exception:
        pass
    return {"ok": True, "expires_at": expires_at.isoformat() if expires_at else None, "issuer": issuer}


async def _check_domain(domain: dict) -> None:
    """One full audit pass on one custom domain."""
    db = get_db()
    hostname = domain.get("domain")
    if not hostname:
        return
    workspace_id = domain.get("workspace_id")
    app_id = domain.get("app_id")
    audit_at = _now().isoformat()

    # ── SSL probe ──
    probe = await _probe_ssl(hostname)
    audit_set: dict = {
        "last_ssl_audit_at": audit_at,
        "last_ssl_audit": probe,
    }
    if not probe.get("ok"):
        # ssl_invalid event — dispatcher applies its own 6h cooldown.
        await dispatch_event(
            workspace_id=workspace_id,
            event_type="ssl_invalid",
            title=f"SSL problem on {hostname}",
            body=f"HTTPS check failed: {probe.get('reason')}. Detail: {probe.get('detail') or '—'}",
            app_id=app_id,
        )
        audit_set["ssl_status"] = "invalid"
    else:
        # Soon-to-expire SSL — fire `ssl_invalid` so the user has time to
        # fix Let's Encrypt rotation before it hard-fails.
        exp = probe.get("expires_at")
        if exp:
            try:
                exp_dt = datetime.fromisoformat(exp)
                days_left = (exp_dt - _now()).days
                audit_set["ssl_expires_at"] = exp
                audit_set["ssl_days_left"] = days_left
                if days_left <= SSL_EXPIRY_WARNING_DAYS:
                    await dispatch_event(
                        workspace_id=workspace_id,
                        event_type="ssl_invalid",
                        title=f"SSL cert expiring on {hostname}",
                        body=f"The HTTPS certificate expires in {days_left} day(s) ({exp}). It should renew automatically — investigate if it doesn't.",
                        app_id=app_id,
                    )
            except (ValueError, TypeError):
                pass
        audit_set["ssl_status"] = "active"

    # ── Domain registration expiry — only fires if WHOIS gave us a date ──
    reg_expires = domain.get("expires_at") or domain.get("registrar_expires_at")
    if reg_expires:
        try:
            reg_dt = datetime.fromisoformat(reg_expires.replace("Z", "+00:00")) if isinstance(reg_expires, str) else reg_expires
            days_left = (reg_dt - _now()).days
            audit_set["registrar_days_left"] = days_left
            if days_left <= DOMAIN_EXPIRY_WARNING_DAYS and days_left >= 0:
                await dispatch_event(
                    workspace_id=workspace_id,
                    event_type="domain_expiring",
                    title=f"{hostname} expires in {days_left} day(s)",
                    body=f"Renew the domain at your registrar before {reg_expires} to keep the site online.",
                    app_id=app_id,
                )
            elif days_left < 0:
                await dispatch_event(
                    workspace_id=workspace_id,
                    event_type="domain_expiring",
                    title=f"{hostname} has expired",
                    body=f"The domain registration expired {-days_left} day(s) ago. Renew immediately.",
                    app_id=app_id,
                )
        except (ValueError, TypeError, AttributeError):
            pass

    await db.domains.update_one({"id": domain["id"]}, {"$set": audit_set})


async def health_audit_tick() -> dict:
    """Scheduler entrypoint. Runs every 6h. Audits every verified custom
    domain. Skips unverified ones — they have no SSL to check yet."""
    db = get_db()
    domains = await db.domains.find(
        {"dns_verified": True},
        {"_id": 0},
    ).to_list(5000)
    if not domains:
        return {"checked": 0}
    logger.info("health-audit: probing %d custom domains", len(domains))
    # Run probes in parallel but cap concurrency so we don't open 500
    # sockets at once.
    sem = asyncio.Semaphore(10)
    async def guarded(d):
        async with sem:
            try:
                await _check_domain(d)
            except Exception as e:
                logger.warning("health-audit: domain=%s failed: %s", d.get("domain"), e)
    await asyncio.gather(*[guarded(d) for d in domains])
    return {"checked": len(domains)}
