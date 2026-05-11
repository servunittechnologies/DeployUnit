"""Automated subdomain provisioning.

When an admin has configured Cloudflare (zone id + API token + target IP/host)
under Admin → Platform Domain, every new app gets a free `{slug}.zone_name`
subdomain with a DNS record created on the fly.

Public entrypoints:
  * provision_subdomain(app)  → {fqdn, record_id} or None
  * release_subdomain(app)    → bool

Failures degrade gracefully — the app is still created without the free
subdomain so deployments are never blocked by DNS hiccups.
"""
import logging
from typing import Optional

from clients.cloudflare import create_dns_record, delete_dns_record
from routers.admin import get_cloudflare_config

logger = logging.getLogger(__name__)


async def provision_subdomain(app: dict) -> Optional[dict]:
    """Create `{slug}.zone_name` pointing at the admin-configured target.
    Returns {fqdn, primary_url, record_id, record_type} on success.

    Order of preference:
      1. CNAME → target_host (good for HA setups)
      2. A     → target_ip
    """
    cfg = await get_cloudflare_config()
    if not cfg:
        return None
    if not (cfg.get("target_host") or cfg.get("target_ip")):
        logger.info("cloudflare: zone configured but no target IP/host; skipping")
        return None
    slug = app.get("slug")
    if not slug:
        return None
    fqdn = f"{slug}.{cfg['zone_name']}"
    # Prefer CNAME if a hostname is provided; fall back to A
    if cfg.get("target_host"):
        record_type, content = "CNAME", cfg["target_host"]
    else:
        record_type, content = "A", cfg["target_ip"]
    rec = await create_dns_record(
        token=cfg["token"],
        zone_id=cfg["zone_id"],
        name=fqdn,
        record_type=record_type,
        content=content,
    )
    if not rec or not rec.get("id"):
        logger.warning("cloudflare: failed to create DNS record for %s", fqdn)
        return None
    return {
        "fqdn": fqdn,
        "primary_url": f"https://{fqdn}",
        "record_id": rec["id"],
        "record_type": record_type,
    }


async def release_subdomain(app: dict) -> bool:
    """Delete the DNS record we created on app create. Idempotent."""
    record_id = app.get("cloudflare_dns_record_id")
    if not record_id:
        return True
    cfg = await get_cloudflare_config()
    if not cfg:
        return False
    return await delete_dns_record(
        token=cfg["token"], zone_id=cfg["zone_id"], record_id=record_id,
    )
