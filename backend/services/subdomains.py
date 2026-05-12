"""Automated subdomain provisioning with pre-warmed pool.

When an admin configures Cloudflare (zone id + API token + target IP/host)
under Admin → Platform Domain, the platform keeps a small POOL of pre-created
DNS records waiting in `cloudflare_subdomain_pool`. New apps grab one from
that pool instantly — DNS has already propagated worldwide, so the URL works
the moment the deploy goes live (no waiting on resolvers).

Public entrypoints:
  * provision_subdomain(app)  → {fqdn, record_id} or None — claims from pool
                                  first, falls back to on-demand DNS create
  * release_subdomain(app)    → bool — deletes the DNS record
  * refill_pool(target=10)    → int  — invoked by the monitor every few mins
                                       to keep the pool topped up
  * pool_stats()              → {free, claimed} — for the admin diagnostic
"""
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from clients.cloudflare import create_dns_record, delete_dns_record
from db import get_db
from routers.admin import get_cloudflare_config

logger = logging.getLogger(__name__)


# Lowercase + digits only. Skip 0/o/1/l-look-alikes to keep URLs typeable.
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"

POOL_COLLECTION = "cloudflare_subdomain_pool"
POOL_TARGET_DEFAULT = 10           # platform-settings override: subdomain_pool_target
POOL_TARGET_HARD_MAX = 50          # safety cap so a typo can't burn the Cloudflare quota


def _random_slug(length: int = 8) -> str:
    """Generate a random, URL-safe subdomain prefix."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _pool_target() -> int:
    """Resolve the desired pool size from platform_settings (admin-tunable),
    falling back to POOL_TARGET_DEFAULT. Always clamped to [0, HARD_MAX]."""
    from routers.admin import get_platform_settings
    doc = await get_platform_settings()
    raw = doc.get("subdomain_pool_target")
    try:
        val = int(raw) if raw is not None else POOL_TARGET_DEFAULT
    except (TypeError, ValueError):
        val = POOL_TARGET_DEFAULT
    return max(0, min(POOL_TARGET_HARD_MAX, val))


async def _create_one(cfg: dict) -> Optional[dict]:
    """Create a single DNS record on Cloudflare. Returns the entry dict."""
    cf_slug = _random_slug()
    fqdn = f"{cf_slug}.{cfg['zone_name']}"
    if cfg.get("target_host"):
        record_type, content = "CNAME", cfg["target_host"]
    else:
        record_type, content = "A", cfg["target_ip"]
    rec = await create_dns_record(
        token=cfg["token"], zone_id=cfg["zone_id"],
        name=fqdn, record_type=record_type, content=content,
    )
    if not rec or not rec.get("id"):
        return None
    return {
        "fqdn": fqdn,
        "primary_url": f"https://{fqdn}",
        "record_id": rec["id"],
        "record_type": record_type,
        "cf_slug": cf_slug,
    }


async def refill_pool(target: int | None = None) -> int:
    """Top the pool up to the configured target. Returns how many we added.

    Called periodically by the monitor worker. Also safe to call from an
    admin endpoint or a one-off script after Cloudflare has been (re)configured.

    If `target` is None we resolve it from platform_settings (admin-editable).
    """
    cfg = await get_cloudflare_config()
    if not cfg:
        return 0
    if not (cfg.get("target_host") or cfg.get("target_ip")):
        logger.info("subdomain pool: cloudflare zone configured but no target IP/host; skipping refill")
        return 0
    if target is None:
        target = await _pool_target()
    if target <= 0:
        return 0
    db = get_db()
    free = await db[POOL_COLLECTION].count_documents({"status": "free"})
    need = max(0, target - free)
    if need == 0:
        return 0
    logger.info("subdomain pool: refilling %d entries (current free=%d, target=%d)", need, free, target)
    added = 0
    for _ in range(need):
        entry = await _create_one(cfg)
        if not entry:
            logger.warning("subdomain pool: refill aborted after %d (DNS create failed)", added)
            break
        await db[POOL_COLLECTION].insert_one({
            **entry,
            "id": entry["record_id"],   # use the Cloudflare record id as our pk
            "status": "free",
            "zone_id": cfg["zone_id"],
            "zone_name": cfg["zone_name"],
            "created_at": _now(),
        })
        added += 1
    return added


async def provision_subdomain(app: dict) -> Optional[dict]:
    """Hand a pre-warmed subdomain from the pool to this app (instant + already
    propagated). Falls back to on-demand creation if the pool is empty.
    Returns {fqdn, primary_url, record_id, record_type, cf_slug}.
    """
    db = get_db()
    # 1) Try to claim from the pool — atomic find-and-update so two parallel
    #    app creations never get the same slug.
    claimed = await db[POOL_COLLECTION].find_one_and_update(
        {"status": "free"},
        {"$set": {
            "status": "claimed",
            "claimed_at": _now(),
            "app_id": app.get("id"),
        }},
        projection={"_id": 0, "status": 0, "claimed_at": 0},
        sort=[("created_at", 1)],  # FIFO — give the oldest (most propagated) first
    )
    if claimed:
        logger.info("subdomain pool: assigned %s to app=%s", claimed["fqdn"], app.get("id"))
        return {
            "fqdn": claimed["fqdn"],
            "primary_url": claimed["primary_url"],
            "record_id": claimed["record_id"],
            "record_type": claimed.get("record_type"),
            "cf_slug": claimed.get("cf_slug"),
        }
    # 2) Pool was empty — create one on demand (DNS will still need to
    #    propagate but better than nothing).
    cfg = await get_cloudflare_config()
    if not cfg or not (cfg.get("target_host") or cfg.get("target_ip")):
        return None
    logger.warning("subdomain pool: empty, falling back to on-demand DNS create for app=%s", app.get("id"))
    entry = await _create_one(cfg)
    if not entry:
        return None
    # Also record this as claimed (so release_subdomain works uniformly).
    await db[POOL_COLLECTION].insert_one({
        **entry,
        "id": entry["record_id"],
        "status": "claimed",
        "zone_id": cfg["zone_id"],
        "zone_name": cfg["zone_name"],
        "created_at": _now(),
        "claimed_at": _now(),
        "app_id": app.get("id"),
        "on_demand": True,
    })
    return entry


async def release_subdomain(app: dict) -> bool:
    """Delete the DNS record we issued for this app. Idempotent."""
    record_id = app.get("cloudflare_dns_record_id")
    if not record_id:
        return True
    cfg = await get_cloudflare_config()
    if not cfg:
        return False
    ok = await delete_dns_record(
        token=cfg["token"], zone_id=cfg["zone_id"], record_id=record_id,
    )
    db = get_db()
    if ok:
        await db[POOL_COLLECTION].delete_one({"record_id": record_id})
    return ok


async def pool_stats() -> dict:
    db = get_db()
    free = await db[POOL_COLLECTION].count_documents({"status": "free"})
    claimed = await db[POOL_COLLECTION].count_documents({"status": "claimed"})
    target = await _pool_target()
    # 5 most recent free entries — gives the admin a peek at upcoming URLs.
    upcoming = await db[POOL_COLLECTION].find(
        {"status": "free"},
        {"_id": 0, "fqdn": 1, "created_at": 1},
        sort=[("created_at", 1)],
    ).limit(5).to_list(5)
    cfg = await get_cloudflare_config()
    ready = bool(cfg and (cfg.get("target_host") or cfg.get("target_ip")))
    return {
        "free": free,
        "claimed": claimed,
        "target": target,
        "hard_max": POOL_TARGET_HARD_MAX,
        "cloudflare_ready": ready,
        "zone_name": cfg.get("zone_name") if cfg else None,
        "upcoming": upcoming,
    }
