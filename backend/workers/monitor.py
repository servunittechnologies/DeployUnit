"""Background monitoring worker.

Runs every 60 seconds via APScheduler. For every app with a primary URL it
issues an HTTP HEAD/GET, stores the result, evaluates alert rules, and emits
notifications when thresholds are breached. Also syncs in-progress
deployment statuses against Coolify.
"""
import logging
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
import httpx

from db import get_db
from clients.coolify import coolify

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _evaluate_alerts(app: dict, ok: bool, response_ms: int | None):
    """Apply alert rules for an app result."""
    db = get_db()
    rules = await db.alert_rules.find(
        {"workspace_id": app["workspace_id"], "enabled": True,
         "$or": [{"app_id": app["id"]}, {"app_id": None}]},
        {"_id": 0},
    ).to_list(50)
    for rule in rules:
        triggered = False
        title = ""
        msg = ""
        if rule["type"] == "app_down" and not ok:
            triggered = True
            title = f"{app['name']} is DOWN"
            msg = f"{app.get('primary_url') or app['name']} returned an error response."
        elif rule["type"] == "slow_response" and response_ms and rule.get("threshold") and response_ms > rule["threshold"]:
            triggered = True
            title = f"{app['name']} responding slowly"
            msg = f"Response time {response_ms}ms exceeds threshold {rule['threshold']}ms."
        if not triggered:
            continue
        # Cooldown
        last = rule.get("last_triggered_at")
        if last:
            last_dt = datetime.fromisoformat(last) if isinstance(last, str) else last
            if (datetime.now(timezone.utc) - last_dt).total_seconds() < rule.get("cooldown_seconds", 600):
                continue
        await db.alert_rules.update_one(
            {"id": rule["id"]}, {"$set": {"last_triggered_at": _now_iso()}}
        )
        await db.notifications.insert_one(
            {
                "id": str(uuid.uuid4()),
                "workspace_id": app["workspace_id"],
                "user_id": None,
                "type": rule["type"],
                "title": title,
                "message": msg,
                "severity": "error" if rule["type"] == "app_down" else "warning",
                "read": False,
                "link": f"/app/apps/{app['id']}",
                "created_at": _now_iso(),
            }
        )


async def _check_app(client: httpx.AsyncClient, app: dict):
    db = get_db()
    url = app.get("primary_url")
    if not url:
        return
    started = datetime.now(timezone.utc)
    ok = False
    status = None
    try:
        r = await client.get(url, follow_redirects=True, timeout=10.0)
        status = r.status_code
        ok = 200 <= r.status_code < 500
    except Exception:
        ok = False
        status = None
    elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    await db.monitoring_results.insert_one(
        {
            "id": str(uuid.uuid4()),
            "app_id": app["id"],
            "workspace_id": app["workspace_id"],
            "timestamp": _now_iso(),
            "status_code": status,
            "response_time_ms": elapsed,
            "ok": ok,
        }
    )
    # purge older than 7 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    await db.monitoring_results.delete_many({"app_id": app["id"], "timestamp": {"$lt": cutoff}})
    await _evaluate_alerts(app, ok, elapsed)


async def run_monitor_tick():
    db = get_db()
    apps = await db.apps.find(
        {"status": {"$in": ["live", "building"]}, "primary_url": {"$ne": None}}, {"_id": 0}
    ).to_list(500)
    if not apps:
        return
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*[_check_app(client, a) for a in apps], return_exceptions=True)


async def sync_deployments():
    """Reconcile in-flight deployments with Coolify (or stub-complete when no Coolify uuid)."""
    db = get_db()
    cutoff_old = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()

    # 1) Stub-complete deployments for apps that have no Coolify uuid.
    # This covers both: Coolify not configured, and seeded apps that never
    # got created in Coolify.
    apps_without_uuid = await db.apps.find(
        {"$or": [{"coolify_app_uuid": None}, {"coolify_app_uuid": {"$exists": False}}]},
        {"_id": 0, "id": 1},
    ).to_list(2000)
    app_ids_no_uuid = [a["id"] for a in apps_without_uuid]
    if app_ids_no_uuid:
        cur = db.deployments.find(
            {"status": {"$in": ["queued", "building"]},
             "started_at": {"$lt": cutoff_old},
             "app_id": {"$in": app_ids_no_uuid}},
            {"_id": 0},
        )
        async for d in cur:
            await db.deployments.update_one(
                {"id": d["id"]},
                {"$set": {
                    "status": "live",
                    "finished_at": _now_iso(),
                    "logs": (d.get("logs") or []) + ["[BUILD] stub build complete", "[STATUS] live"],
                }},
            )
            await db.apps.update_one(
                {"id": d["app_id"]},
                {"$set": {
                    "status": "live",
                    "primary_url": f"https://{d['app_id'][:8]}.deploy.example",
                    "last_deploy_at": _now_iso(),
                }},
            )

    if not coolify.configured:
        return

    # 2) Real Coolify reconcile for apps that DO have a uuid.
    apps = await db.apps.find(
        {"coolify_app_uuid": {"$ne": None}, "status": {"$in": ["queued", "building"]}}, {"_id": 0}
    ).to_list(200)
    for a in apps:
        info = await coolify.get_application(a["coolify_app_uuid"])
        if not info:
            continue
        cool_status = (info.get("status") or "").lower()
        new_status = "building"
        # Coolify status strings include: "running:healthy", "running:unhealthy",
        # "exited:0", "exited:1", "exited:unhealthy", "starting", "restarting".
        if cool_status.startswith("running"):
            new_status = "live"
        elif "exited:0" in cool_status:
            new_status = "live"
        elif "exited" in cool_status or "fail" in cool_status or "error" in cool_status:
            # exited:1, exited:unhealthy, exited:* — mark failed
            new_status = "failed"
        fqdn = info.get("fqdn") or info.get("preview_fqdn")
        primary_url = None
        if fqdn:
            primary_url = fqdn if fqdn.startswith("http") else f"https://{fqdn.split(',')[0]}"
        update = {"status": new_status}
        if primary_url:
            update["primary_url"] = primary_url
        if new_status in ("live", "failed"):
            update["last_deploy_at"] = _now_iso()
        await db.apps.update_one({"id": a["id"]}, {"$set": update})
        await db.deployments.update_many(
            {"app_id": a["id"], "status": {"$in": ["queued", "building"]}},
            {"$set": {"status": new_status, "finished_at": _now_iso() if new_status != "building" else None}},
        )
