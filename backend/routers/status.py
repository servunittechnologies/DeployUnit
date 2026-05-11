"""Public status page — pings every dependency, surfaces uptime + incidents.

Public endpoints (no auth):
  GET  /api/status                — summary + per-component status + incidents
  GET  /api/status/components     — flat list (for embedding)
  GET  /api/status/history?days=N — daily uptime buckets

Background:
  APScheduler `status_ping_tick` runs every 60s and pings each component.
"""
import os
import time
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Callable, Awaitable

import httpx
from fastapi import APIRouter

from db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["status"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ────────────────── Component check functions ──────────────────
async def _http_check(url: str, *, method: str = "GET", timeout: float = 6.0) -> dict:
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
            r = await c.request(method, url)
        latency = (time.monotonic() - t0) * 1000
        ok = r.status_code < 500  # 4xx still counts as "service reachable"
        return {"ok": ok, "latency_ms": round(latency, 1), "status_code": r.status_code,
                "error": None if ok else f"HTTP {r.status_code}"}
    except Exception as e:
        return {"ok": False, "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                "error": type(e).__name__}


async def check_api() -> dict:
    # We are the API — if this code runs, the API responds.
    return {"ok": True, "latency_ms": 1.0, "error": None}


async def check_db() -> dict:
    t0 = time.monotonic()
    try:
        await get_db().command("ping")
        return {"ok": True, "latency_ms": round((time.monotonic() - t0) * 1000, 1), "error": None}
    except Exception as e:
        return {"ok": False, "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                "error": type(e).__name__}


async def check_coolify() -> dict:
    db = get_db()
    ps = await db.platform_settings.find_one({"id": "platform-singleton"},
                                              {"_id": 0, "coolify_base_url": 1}) or {}
    base = (ps.get("coolify_base_url") or "").rstrip("/")
    if not base:
        return {"ok": True, "latency_ms": 0, "error": None, "skipped": True, "note": "not configured"}
    return await _http_check(f"{base}/api/health")


async def check_mollie() -> dict:
    return await _http_check("https://api.mollie.com/v2/", timeout=8)


async def check_github() -> dict:
    return await _http_check("https://api.github.com/zen", timeout=5)


async def check_cloudflare() -> dict:
    return await _http_check("https://api.cloudflare.com/client/v4/", timeout=5)


async def check_mailersend() -> dict:
    return await _http_check("https://api.mailersend.com/v1/", timeout=5)


async def check_twilio() -> dict:
    return await _http_check("https://status.twilio.com/api/v2/status.json", timeout=5)


async def check_self(url: str) -> dict:
    return await _http_check(url, timeout=4)


COMPONENTS = [
    {"id": "api",        "name": "DeployHub API",      "desc": "Public REST API and dashboard backend",  "group": "Core"},
    {"id": "db",         "name": "Database",           "desc": "MongoDB primary cluster",                "group": "Core"},
    {"id": "tracker",    "name": "Web analytics",      "desc": "Pageview tracker endpoint",              "group": "Core"},
    {"id": "metrics",    "name": "Metrics ingest",     "desc": "VPS agent ingestion pipeline",           "group": "Core"},
    {"id": "coolify",    "name": "Deployment engine",  "desc": "Container build & deploy backend",       "group": "Infrastructure"},
    {"id": "github",     "name": "GitHub integration", "desc": "OAuth + push-to-deploy",                  "group": "Integrations"},
    {"id": "cloudflare", "name": "DNS provider",       "desc": "Custom domains + DNS automation",         "group": "Integrations"},
    {"id": "mollie",     "name": "Payments",           "desc": "Subscriptions + EU VAT (Mollie)",         "group": "Integrations"},
    {"id": "mailersend", "name": "Email delivery",     "desc": "Transactional email (MailerSend)",        "group": "Integrations"},
    {"id": "twilio",     "name": "SMS & WhatsApp",     "desc": "Twilio alert channel",                    "group": "Integrations"},
]


def _checks_map(public_base: str) -> dict[str, Callable[[], Awaitable[dict]]]:
    return {
        "api":        check_api,
        "db":         check_db,
        "tracker":    lambda: check_self(f"{public_base}/api/analytics/tracker.js"),
        "metrics":    lambda: check_self(f"{public_base}/api/agent/install.sh"),
        "coolify":    check_coolify,
        "github":     check_github,
        "cloudflare": check_cloudflare,
        "mollie":     check_mollie,
        "mailersend": check_mailersend,
        "twilio":     check_twilio,
    }


# ────────────────── Background pings ──────────────────
async def status_ping_tick() -> dict:
    """Run every component check concurrently, store the result, update
    open-incident state on edge transitions."""
    db = get_db()
    public_base = (os.environ.get("FRONTEND_URL") or "").rstrip("/")
    checks = _checks_map(public_base)
    now = _now()
    now_iso = now.isoformat()

    async def run_one(cid: str):
        fn = checks[cid]
        try:
            return cid, await fn()
        except Exception as e:
            return cid, {"ok": False, "error": type(e).__name__, "latency_ms": 0}

    results = await asyncio.gather(*[run_one(c["id"]) for c in COMPONENTS])
    docs = []
    for cid, r in results:
        docs.append({
            "id": str(uuid.uuid4()),
            "component_id": cid,
            "ts": now_iso,
            "day": now.strftime("%Y-%m-%d"),
            "ok": bool(r.get("ok")),
            "latency_ms": float(r.get("latency_ms") or 0),
            "error": r.get("error"),
            "skipped": bool(r.get("skipped")),
            "status_code": r.get("status_code"),
        })
    if docs:
        await db.status_pings.insert_many(docs)

    # Auto-incident creation: if a component is down for 2 consecutive pings,
    # open an incident. Close it on first successful ping.
    for cid, r in results:
        ok = bool(r.get("ok"))
        # Get the open incident (if any)
        open_inc = await db.status_incidents.find_one(
            {"component_id": cid, "resolved_at": None},
            {"_id": 0},
            sort=[("started_at", -1)],
        )
        if not ok and not open_inc:
            # Need 2 consecutive failures to declare an incident — avoids
            # flapping. Check the previous ping.
            prev = await db.status_pings.find_one(
                {"component_id": cid, "ts": {"$lt": now_iso}},
                {"_id": 0, "ok": 1},
                sort=[("ts", -1)],
            )
            if prev and not prev.get("ok"):
                await db.status_incidents.insert_one({
                    "id": str(uuid.uuid4()),
                    "component_id": cid,
                    "started_at": now_iso,
                    "resolved_at": None,
                    "severity": "major" if cid in {"api", "db", "tracker"} else "minor",
                    "summary": f"{cid} unreachable: {r.get('error', 'unknown')}",
                })
        elif ok and open_inc:
            await db.status_incidents.update_one(
                {"id": open_inc["id"]},
                {"$set": {"resolved_at": now_iso}},
            )

    # GC raw pings older than 95 days
    cut = (now - timedelta(days=95)).isoformat()
    await db.status_pings.delete_many({"ts": {"$lt": cut}})
    return {"ran": len(results)}


# ────────────────── Aggregations ──────────────────
async def _latest_ping(component_id: str) -> dict | None:
    db = get_db()
    return await db.status_pings.find_one(
        {"component_id": component_id},
        {"_id": 0},
        sort=[("ts", -1)],
    )


async def _uptime_history(component_id: str, days: int = 90) -> list[dict]:
    """Returns one bucket per day for the last `days` days with uptime %."""
    db = get_db()
    since = (_now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    cur = db.status_pings.aggregate([
        {"$match": {"component_id": component_id, "day": {"$gte": since}}},
        {"$group": {"_id": "$day",
                    "total": {"$sum": 1},
                    "okc":   {"$sum": {"$cond": ["$ok", 1, 0]}}}},
        {"$project": {"_id": 0, "day": "$_id", "total": 1, "okc": 1}},
        {"$sort": {"day": 1}},
    ])
    rows = await cur.to_list(days + 1)
    return rows


def _state(latest: dict | None) -> str:
    if not latest:
        return "unknown"
    if not latest.get("ok"):
        return "down"
    if (latest.get("latency_ms") or 0) > 1500:
        return "degraded"
    return "operational"


# ────────────────── Public endpoints ──────────────────
@router.get("/status")
async def public_status():
    out = []
    overall_state = "operational"
    for c in COMPONENTS:
        latest = await _latest_ping(c["id"])
        state = _state(latest)
        if state == "down":
            overall_state = "down"
        elif state == "degraded" and overall_state == "operational":
            overall_state = "degraded"
        out.append({
            **c,
            "state": state,
            "latency_ms": (latest or {}).get("latency_ms"),
            "last_checked_at": (latest or {}).get("ts"),
            "error": (latest or {}).get("error"),
        })

    # Incidents — open + last 10 resolved
    db = get_db()
    open_cur = db.status_incidents.find({"resolved_at": None}, {"_id": 0}).sort("started_at", -1)
    open_inc = await open_cur.to_list(20)
    resolved_cur = db.status_incidents.find({"resolved_at": {"$ne": None}}, {"_id": 0}).sort("started_at", -1).limit(10)
    resolved = await resolved_cur.to_list(10)

    return {
        "overall_state": overall_state,
        "checked_at": _now().isoformat(),
        "components": out,
        "open_incidents": open_inc,
        "recent_incidents": resolved,
    }


@router.get("/status/components")
async def status_components():
    """Compact list (without incident bundle) — handy for embedding."""
    payload = await public_status()
    return {"overall_state": payload["overall_state"], "components": payload["components"]}


@router.get("/status/history")
async def status_history(days: int = 90):
    days = max(1, min(int(days), 90))
    out = {}
    for c in COMPONENTS:
        rows = await _uptime_history(c["id"], days=days)
        out[c["id"]] = rows
    return {"days": days, "history": out}
