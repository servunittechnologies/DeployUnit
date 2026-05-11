"""Agency Fleet View — multi-client overview for studios/agencies.

Surfaces every workspace the current user belongs to, with each workspace's
apps, problem-first sorted (failures → down → building → live), plus per-
workspace KPIs (apps, credits, plan, monthly cost). One endpoint powers the
entire dashboard.

Gated by plan.fleet_view in services/plans.py. Free/Pro plans see a paywall;
Agency plan unlocks the view.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request

from db import get_db
from auth_utils import get_current_user
from services.plans import workspace_plan

router = APIRouter(tags=["fleet"])
logger = logging.getLogger(__name__)


# Problem-first sort: lower number = bubble to top
_STATUS_RANK = {
    "failed": 0,
    "error": 0,
    "down": 1,
    "queued": 2,
    "building": 3,
    "deploying": 3,
    "live": 4,
    "ok": 4,
    "stopped": 5,
}


def _rank(status: str) -> int:
    return _STATUS_RANK.get((status or "").lower(), 6)


def _ts(iso: Optional[str]) -> float:
    """Best-effort ISO-8601 → epoch seconds. Returns 0.0 on anything malformed
    so the sort never crashes the entire endpoint."""
    if not iso:
        return 0.0
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return 0.0


async def _user_accessible_workspaces(user: dict) -> list[dict]:
    """Workspaces the user owns OR is an explicit member of."""
    db = get_db()
    user_id = user["id"]
    owned = await db.workspaces.find({"owner_id": user_id}, {"_id": 0}).to_list(200)
    member_ids = await db.workspace_members.find(
        {"user_id": user_id}, {"_id": 0, "workspace_id": 1}
    ).to_list(500)
    member_ids = [m["workspace_id"] for m in member_ids]
    if member_ids:
        extra = await db.workspaces.find(
            {"id": {"$in": member_ids}, "owner_id": {"$ne": user_id}},
            {"_id": 0},
        ).to_list(200)
    else:
        extra = []
    return owned + extra


@router.get("/fleet/overview")
async def fleet_overview(request: Request):
    """Aggregated multi-workspace dashboard for agencies. Each entry includes:
        - workspace meta (id, name, type)
        - plan + effective price + credits balance
        - apps (problem-first sorted) with status + primary_url + last_deploy
        - rollup KPIs (total_apps, broken_apps, live_apps, total_monthly_eur)
    """
    user = await get_current_user(request)
    db = get_db()

    workspaces = await _user_accessible_workspaces(user)
    if not workspaces:
        return {
            "fleet_view_enabled": False,
            "workspaces": [],
            "rollup": {"workspaces": 0, "apps_total": 0, "apps_broken": 0, "apps_live": 0, "monthly_eur": 0.0},
            "reason": "no workspaces accessible",
        }

    # Determine fleet_view eligibility — granted if ANY accessible workspace
    # is on a plan with fleet_view=true. Keeps single-workspace Pro users out
    # while letting agency-tier users see all their clients in one place.
    plans_cache: dict[str, dict] = {}
    eligible = False
    for ws in workspaces:
        plan = await workspace_plan(ws["id"])
        plans_cache[ws["id"]] = plan
        if plan.get("fleet_view"):
            eligible = True

    if not eligible:
        return {
            "fleet_view_enabled": False,
            "workspaces": [],
            "rollup": {"workspaces": 0, "apps_total": 0, "apps_broken": 0, "apps_live": 0, "monthly_eur": 0.0},
            "reason": "upgrade to Agency plan to unlock Fleet view",
            "upgrade_plan": "agency",
        }

    rollup_apps_total = 0
    rollup_apps_broken = 0
    rollup_apps_live = 0
    rollup_monthly = 0.0

    out_workspaces = []
    for ws in workspaces:
        plan = plans_cache[ws["id"]]
        apps = await db.apps.find(
            {"workspace_id": ws["id"]},
            {
                "_id": 0, "id": 1, "name": 1, "slug": 1, "status": 1,
                "primary_url": 1, "last_deploy_at": 1, "branch": 1,
                "repo_url": 1, "framework": 1,
            },
        ).to_list(500)
        # Decorate each app with the latest monitoring sample (ok/down) when
        # available so the fleet shows real reachability, not just last deploy.
        for app in apps:
            mon = await db.monitoring_results.find_one(
                {"app_id": app["id"]}, {"_id": 0, "ok": 1, "latency_ms": 1, "checked_at": 1},
                sort=[("checked_at", -1)],
            )
            if mon:
                app["health"] = "ok" if mon.get("ok") else "down"
                app["latency_ms"] = mon.get("latency_ms")
                app["last_check_at"] = mon.get("checked_at")
            else:
                app["health"] = None
        # Problem-first sort
        apps.sort(key=lambda a: (
            _rank("down" if a.get("health") == "down" else a.get("status")),
            -_ts(a.get("last_deploy_at")),
        ))
        broken = sum(1 for a in apps if _rank(a.get("status")) <= 1 or a.get("health") == "down")
        live = sum(1 for a in apps if (a.get("status") or "").lower() == "live")
        rollup_apps_total += len(apps)
        rollup_apps_broken += broken
        rollup_apps_live += live
        price = float(plan.get("price") or 0.0)
        rollup_monthly += price

        out_workspaces.append({
            "id": ws["id"],
            "name": ws["name"],
            "type": ws.get("type"),
            "plan": {"id": plan.get("id"), "name": plan.get("name"), "price": price},
            "credits_balance": int(ws.get("credits_balance") or 0),
            "kpi": {
                "apps_total": len(apps),
                "apps_broken": broken,
                "apps_live": live,
            },
            "apps": apps,
        })

    # Workspaces with the most pain bubble to the top of the fleet.
    out_workspaces.sort(key=lambda w: (-w["kpi"]["apps_broken"], -w["kpi"]["apps_total"]))

    return {
        "fleet_view_enabled": True,
        "workspaces": out_workspaces,
        "rollup": {
            "workspaces": len(out_workspaces),
            "apps_total": rollup_apps_total,
            "apps_broken": rollup_apps_broken,
            "apps_live": rollup_apps_live,
            "monthly_eur": round(rollup_monthly, 2),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/fleet/bulk-redeploy")
async def bulk_redeploy(request: Request):
    """Trigger a redeploy for every accessible app whose status is failed/down.
    Returns # of deploys queued. Rate-limited at 50/call to protect the build
    engine; if you have more failures than that, fix infra first."""
    import asyncio
    import uuid
    from routers.apps import _redeploy_background

    user = await get_current_user(request)
    db = get_db()

    workspaces = await _user_accessible_workspaces(user)
    if not workspaces:
        raise HTTPException(status_code=404, detail="no workspaces accessible")

    # Honor the same fleet_view gate as overview.
    eligible = False
    for ws in workspaces:
        plan = await workspace_plan(ws["id"])
        if plan.get("fleet_view"):
            eligible = True
            break
    if not eligible:
        raise HTTPException(status_code=402, detail="upgrade to Agency plan to use bulk-redeploy")

    ws_ids = [w["id"] for w in workspaces]
    # All "broken" apps including those that never reached the build engine.
    candidates = await db.apps.find(
        {
            "workspace_id": {"$in": ws_ids},
            "status": {"$in": ["failed", "error", "down"]},
        },
        {"_id": 0, "id": 1, "workspace_id": 1, "coolify_app_uuid": 1, "branch": 1},
    ).limit(50).to_list(50)
    # Skip ones that never reached the build engine — _redeploy_background
    # requires a coolify_app_uuid.
    apps = [a for a in candidates if a.get("coolify_app_uuid")]
    skipped = len(candidates) - len(apps)

    queued = []
    for app in apps:
        deploy_id = str(uuid.uuid4())
        await db.deployments.insert_one({
            "id": deploy_id,
            "app_id": app["id"],
            "workspace_id": app["workspace_id"],
            "status": "queued",
            "commit_sha": None,
            "commit_message": "Bulk redeploy from Fleet view",
            "branch": app.get("branch") or "main",
            "trigger": "fleet_bulk",
            "logs": ["[QUEUE] bulk redeploy from Fleet view"],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
        })
        # Fire-and-forget — _redeploy_background is already idempotent.
        asyncio.create_task(_redeploy_background(app["id"], deploy_id, app["coolify_app_uuid"], None))
        queued.append({"app_id": app["id"], "deployment_id": deploy_id})

    return {"queued": len(queued), "skipped": skipped, "deployments": queued}
