"""Monitoring routes — uptime + response time stats + usage analytics."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from services.usage_analytics import app_analytics, account_analytics

router = APIRouter(tags=["monitoring"])


@router.get("/apps/{app_id}/analytics")
async def get_app_analytics(app_id: str, request: Request, window: str = "24h"):
    """Aggregate everything we can measure for one app:
      - uptime % + samples count
      - average + p95 response time
      - bucketed time-series (response_ms + uptime_pct)
      - status timeline (live/down/building windows)
      - deployments in window + build minutes
      - currently allocated resources (cpu/mem/storage + addon cost)
    `window` is one of 1h / 24h / 7d / 30d.
    """
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0, "workspace_id": 1})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    return await app_analytics(app_id, window=window)


@router.get("/account/analytics")
async def get_account_analytics(request: Request, window: str = "30d"):
    """Roll-up across every workspace the user owns — total resources
    allocated, build minutes used, credit burn per category, headroom etc."""
    user = await get_current_user(request)
    return await account_analytics(user["id"], window=window)


@router.get("/apps/{app_id}/monitoring")
async def app_monitoring(app_id: str, request: Request, hours: int = 24):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = await db.monitoring_results.find(
        {"app_id": app_id, "timestamp": {"$gte": cutoff}}, {"_id": 0}
    ).sort("timestamp", -1).to_list(2000)

    if not rows:
        return {
            "uptime_pct": None,
            "avg_response_ms": None,
            "samples": 0,
            "results": [],
        }
    ok = sum(1 for r in rows if r.get("ok"))
    rt = [r["response_time_ms"] for r in rows if r.get("response_time_ms") is not None]
    return {
        "uptime_pct": round(100 * ok / len(rows), 2),
        "avg_response_ms": round(sum(rt) / len(rt)) if rt else None,
        "samples": len(rows),
        "results": rows[:300],
    }


@router.get("/monitoring/overview")
async def workspace_overview(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    apps = await db.apps.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(500)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    out = []
    for a in apps:
        rows = await db.monitoring_results.find(
            {"app_id": a["id"], "timestamp": {"$gte": cutoff}}, {"_id": 0}
        ).to_list(2000)
        if rows:
            ok = sum(1 for r in rows if r.get("ok"))
            rt = [r["response_time_ms"] for r in rows if r.get("response_time_ms") is not None]
            uptime = round(100 * ok / len(rows), 2)
            avg_ms = round(sum(rt) / len(rt)) if rt else None
        else:
            uptime, avg_ms = None, None
        out.append({
            "app_id": a["id"],
            "name": a["name"],
            "status": a.get("status"),
            "primary_url": a.get("primary_url"),
            "uptime_pct": uptime,
            "avg_response_ms": avg_ms,
        })
    return out
