"""Self-hosted, cookieless web analytics — pageviews + sessions + top-pages.

Privacy-first design:
* No cookies. Visitor identity = sha256(ip + ua + site_id + utc_day_iso),
  rotating every day so we can't long-track an individual.
* Country lookup from `cf-ipcountry` / `x-vercel-ip-country` headers
  (free when behind Cloudflare). Falls back to "??" otherwise.
* Bot filter via UA heuristics.

Storage: `analytics_events` collection. Raw events for 90 days.
"""
import re
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import get_db

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today_key() -> str:
    return _now().strftime("%Y-%m-%d")


BOT_RE = re.compile(r"(bot|crawler|spider|preview|monitor|insights|lighthouse|pagespeed|headless|wget|curl)",
                    re.IGNORECASE)


def is_bot(ua: str) -> bool:
    return bool(BOT_RE.search(ua or ""))


def _hash_visitor(ip: str, ua: str, site_id: str) -> str:
    raw = f"{ip}|{ua}|{site_id}|{_today_key()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _device(ua: str) -> str:
    ua = (ua or "").lower()
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if "bot" in ua:
        return "bot"
    return "desktop"


_BROWSERS = [
    ("Edge", r"edg/"),
    ("Chrome", r"chrome/"),
    ("Firefox", r"firefox/"),
    ("Safari", r"safari/"),
    ("Opera", r"opr/|opera/"),
]


def _browser(ua: str) -> str:
    ua = (ua or "").lower()
    for name, pat in _BROWSERS:
        if re.search(pat, ua):
            return name
    return "Other"


# ────────────────── Config ──────────────────
async def ensure_site_id(app_id: str) -> str:
    """Idempotent: returns the analytics site_id for this app, creating it on first use."""
    db = get_db()
    cfg = await db.app_analytics_config.find_one({"app_id": app_id}, {"_id": 0})
    if cfg and cfg.get("site_id"):
        return cfg["site_id"]
    site_id = "dh_" + uuid.uuid4().hex[:14]
    await db.app_analytics_config.update_one(
        {"app_id": app_id},
        {"$set": {"site_id": site_id, "created_at": _now().isoformat()},
         "$setOnInsert": {"app_id": app_id, "clarity_project_id": None}},
        upsert=True,
    )
    return site_id


async def get_config(app_id: str) -> dict:
    db = get_db()
    cfg = await db.app_analytics_config.find_one({"app_id": app_id}, {"_id": 0}) or {}
    # Platform-wide Clarity project id — set once in Admin → Integrations.
    # Auto-injected on every Pro+ app so customers get heatmaps zero-setup.
    ps = await db.platform_settings.find_one({"id": "platform-singleton"},
                                              {"_id": 0, "clarity_project_id": 1}) or {}
    platform_clarity = (ps.get("clarity_project_id") or "").strip() or None
    return {
        "site_id": cfg.get("site_id"),
        "clarity_project_id": platform_clarity,
        "platform_clarity_configured": bool(platform_clarity),
        "auto_inject_enabled": bool(cfg.get("auto_inject_enabled", False)),
        "created_at": cfg.get("created_at"),
    }


async def set_auto_inject(app_id: str, enabled: bool) -> dict:
    db = get_db()
    await db.app_analytics_config.update_one(
        {"app_id": app_id},
        {"$set": {"auto_inject_enabled": bool(enabled), "updated_at": _now().isoformat()}},
        upsert=True,
    )
    return await get_config(app_id)


async def find_app_by_site(site_id: str) -> Optional[dict]:
    db = get_db()
    cfg = await db.app_analytics_config.find_one({"site_id": site_id}, {"_id": 0, "app_id": 1})
    if not cfg:
        return None
    return await db.apps.find_one({"id": cfg["app_id"]}, {"_id": 0, "id": 1, "workspace_id": 1, "primary_url": 1})


# ────────────────── Ingest ──────────────────
async def track_event(
    *,
    site_id: str,
    path: str,
    referrer: Optional[str],
    user_agent: str,
    language: Optional[str],
    screen: Optional[str],
    event: str,
    ip: str,
    country: Optional[str],
) -> dict:
    db = get_db()
    app = await find_app_by_site(site_id)
    if not app:
        return {"accepted": False, "reason": "unknown_site"}
    if is_bot(user_agent):
        return {"accepted": False, "reason": "bot"}
    doc = {
        "id": str(uuid.uuid4()),
        "app_id": app["id"],
        "workspace_id": app.get("workspace_id"),
        "site_id": site_id,
        "ts": _now().isoformat(),
        "day": _today_key(),
        "path": (path or "/")[:512],
        "referrer": (referrer or "")[:512] or None,
        "ua": (user_agent or "")[:300],
        "browser": _browser(user_agent),
        "device": _device(user_agent),
        "country": (country or "??")[:2].upper(),
        "language": (language or "")[:8] or None,
        "screen": (screen or "")[:20] or None,
        "event": (event or "pageview")[:32],
        "visitor_hash": _hash_visitor(ip, user_agent, site_id),
    }
    await db.analytics_events.insert_one(doc)
    return {"accepted": True}


# ────────────────── Queries ──────────────────
_DELTAS = {"24h": timedelta(hours=24), "7d": timedelta(days=7),
           "30d": timedelta(days=30), "90d": timedelta(days=90)}


async def summary(app_id: str, *, window: str = "7d") -> dict:
    db = get_db()
    delta = _DELTAS.get(window, _DELTAS["7d"])
    since = (_now() - delta).isoformat()
    match = {"app_id": app_id, "ts": {"$gte": since}}

    total_pv = await db.analytics_events.count_documents({**match, "event": "pageview"})
    uniques_cur = db.analytics_events.aggregate([
        {"$match": {**match, "event": "pageview"}},
        {"$group": {"_id": "$visitor_hash"}},
        {"$count": "n"},
    ])
    uniques = 0
    async for r in uniques_cur:
        uniques = r["n"]

    # Time series — daily buckets (or hourly if 24h)
    bucket = "hour" if window == "24h" else "day"
    fmt = "%Y-%m-%dT%H:00" if bucket == "hour" else "%Y-%m-%d"
    series_cur = db.analytics_events.aggregate([
        {"$match": {**match, "event": "pageview"}},
        {"$addFields": {"_ts": {"$dateFromString": {"dateString": "$ts"}}}},
        {"$group": {
            "_id": {"$dateToString": {"format": fmt, "date": "$_ts"}},
            "pv": {"$sum": 1},
            "uniques": {"$addToSet": "$visitor_hash"},
        }},
        {"$project": {"_id": 0, "bucket": "$_id", "pv": 1, "uniques": {"$size": "$uniques"}}},
        {"$sort": {"bucket": 1}},
    ])
    series = await series_cur.to_list(500)

    async def top(field: str, limit: int = 8) -> list[dict]:
        cur = db.analytics_events.aggregate([
            {"$match": {**match, "event": "pageview"}},
            {"$group": {"_id": f"${field}", "n": {"$sum": 1}}},
            {"$match": {"_id": {"$ne": None}}},
            {"$sort": {"n": -1}},
            {"$limit": limit},
            {"$project": {"_id": 0, "key": "$_id", "n": 1}},
        ])
        return await cur.to_list(limit)

    top_pages = await top("path", 10)
    top_referrers = await top("referrer", 10)
    top_countries = await top("country", 12)
    devices = await top("device", 5)
    browsers = await top("browser", 8)

    return {
        "window": window,
        "since": since,
        "totals": {"pageviews": total_pv, "uniques": uniques,
                   "views_per_visitor": round(total_pv / uniques, 2) if uniques else 0.0},
        "series": series,
        "top_pages": top_pages,
        "top_referrers": top_referrers,
        "top_countries": top_countries,
        "devices": devices,
        "browsers": browsers,
        "have_data": total_pv > 0,
    }


async def gc(retention_days: int = 90) -> int:
    db = get_db()
    cut = (_now() - timedelta(days=retention_days)).isoformat()
    res = await db.analytics_events.delete_many({"ts": {"$lt": cut}})
    return res.deleted_count
