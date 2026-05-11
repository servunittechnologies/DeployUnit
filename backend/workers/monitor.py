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
from services.log_parser import extract_failure_summary
from services.whitelabel import sanitize, sanitize_lines

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


async def deployment_watchdog():
    """Pick up deployments that are stuck 'queued' or 'building' for >90s
    without a Coolify deployment_uuid, and retry the /deploy trigger once.

    This is the safety net for the silent-failure case where create_public_app
    succeeded but the subsequent /deploy call never actually made it to the
    Coolify worker. Runs every 15s alongside sync_deployments.
    """
    db = get_db()
    if not coolify.configured:
        return
    cutoff_stuck = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
    stuck = await db.deployments.find(
        {
            "status": {"$in": ["queued", "building"]},
            "started_at": {"$lt": cutoff_stuck},
            "$or": [
                {"coolify_deployment_uuid": None},
                {"coolify_deployment_uuid": {"$exists": False}},
            ],
        },
        {"_id": 0, "id": 1, "app_id": 1, "logs": 1},
    ).limit(25).to_list(25)
    if not stuck:
        return
    for dep in stuck:
        app = await db.apps.find_one({"id": dep["app_id"]})
        if not app or not app.get("coolify_app_uuid"):
            continue
        # Bail out cleanly if the build engine has already lost the app (e.g.
        # it was deleted out of band). Otherwise the watchdog spams forever.
        cool_app = await coolify.get_application(app["coolify_app_uuid"])
        if cool_app is None:
            await db.deployments.update_one(
                {"id": dep["id"]},
                {
                    "$set": {
                        "status": "failed",
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                    },
                    "$push": {"logs": "[WATCHDOG] build-engine app no longer exists — marking deployment failed."},
                },
            )
            logger.info("deployment_watchdog: app %s gone on build engine; failing dep %s", app["id"], dep["id"])
            continue
        logger.info(
            "deployment_watchdog: retrying coolify deploy for %s (app=%s)",
            dep["id"],
            app["id"],
        )
        try:
            res = await coolify.deploy(app["coolify_app_uuid"], force=True)
        except Exception as e:
            res = None
            logger.warning("watchdog deploy raised for %s: %s", dep["id"], e)
        update = {}
        new_logs: list[str] = []
        if res and (res.get("deployment_uuid") or res.get("uuid")):
            cool_uuid = res.get("deployment_uuid") or res.get("uuid")
            update["coolify_deployment_uuid"] = cool_uuid
            update["status"] = "building"
            new_logs.append(f"[WATCHDOG] deploy reconciled (uuid={cool_uuid})")
        else:
            # Count retries so we don't spam forever. After 5 misses (~2.5 min),
            # give up and mark the deploy failed.
            retries = int(dep.get("watchdog_retries") or 0) + 1
            update["watchdog_retries"] = retries
            if retries >= 5:
                update["status"] = "failed"
                update["finished_at"] = datetime.now(timezone.utc).isoformat()
                new_logs.append("[WATCHDOG] giving up after 5 retries — marking deployment failed.")
            else:
                new_logs.append(f"[WATCHDOG] build engine still not returning a deploy id (retry {retries}/5)")
        if update or new_logs:
            patch = {"$set": update} if update else {}
            if new_logs:
                patch.setdefault("$push", {})["logs"] = {"$each": new_logs}
            await db.deployments.update_one({"id": dep["id"]}, patch)


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
    #    Include "failed" here too: a build may have finished successfully on
    #    Coolify after our watchdog gave up early, and we shouldn't leave the
    #    app stranded as "failed" when it's actually running.
    apps = await db.apps.find(
        {"coolify_app_uuid": {"$ne": None},
         "status": {"$in": ["queued", "building", "failed"]}}, {"_id": 0}
    ).to_list(200)
    for a in apps:
        info = await coolify.get_application(a["coolify_app_uuid"])
        if not info:
            continue
        cool_status = (info.get("status") or "").lower()
        # If the app is already marked failed and Coolify still reports
        # exited/failed, leave it alone — no point thrashing.
        is_currently_failed = a.get("status") == "failed"
        new_status = a.get("status") or "building"
        if cool_status.startswith("running"):
            new_status = "live"
        elif "exited:0" in cool_status:
            new_status = "live"
        elif "exited" in cool_status or "fail" in cool_status or "error" in cool_status:
            new_status = "failed"
        elif is_currently_failed and not cool_status:
            # Coolify reports no status at all → keep the failed marker
            continue
        # No state change → skip the write.
        if new_status == a.get("status"):
            continue
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
        # If we just rescued an app from failed → live, also flip the latest
        # deployment row to "live" so the UI history reflects reality.
        if new_status == "live" and is_currently_failed:
            recent_failed = await db.deployments.find_one(
                {"app_id": a["id"], "status": "failed"},
                {"_id": 0, "id": 1},
                sort=[("started_at", -1)],
            )
            if recent_failed:
                await db.deployments.update_one(
                    {"id": recent_failed["id"]},
                    {"$set": {"status": "live", "finished_at": _now_iso()},
                     "$push": {"logs": "[SYNC] build engine finished after watchdog gave up — promoted to live"}},
                )

        # Pull the latest Coolify deployment logs onto our deployment row
        # so the user sees the real failure reason without opening the stream.
        latest_cool_deploys = await coolify.list_deployments(a["coolify_app_uuid"])
        cool_deploy_uuid = None
        cool_log_lines: list[str] = []
        if isinstance(latest_cool_deploys, list) and latest_cool_deploys:
            head = latest_cool_deploys[0]
            if isinstance(head, dict):
                cool_deploy_uuid = head.get("deployment_uuid") or head.get("uuid")
        if cool_deploy_uuid:
            full = await coolify.get_deployment(cool_deploy_uuid)
            if full:
                raw = full.get("logs")
                import json as _json
                if isinstance(raw, str):
                    try:
                        raw = _json.loads(raw)
                    except Exception:
                        raw = [raw]
                if isinstance(raw, list):
                    for item in raw:
                        if isinstance(item, dict):
                            txt = item.get("output") or item.get("message") or ""
                            if txt:
                                cool_log_lines.append(str(txt).rstrip("\n"))
                        elif isinstance(item, str):
                            cool_log_lines.append(item)

        deploy_update: dict = {
            "status": new_status,
            "finished_at": _now_iso() if new_status != "building" else None,
        }
        if cool_log_lines:
            deploy_update["logs"] = sanitize_lines(cool_log_lines)
        if cool_deploy_uuid:
            deploy_update["coolify_deployment_uuid"] = cool_deploy_uuid
        if new_status == "failed":
            summary = extract_failure_summary(cool_log_lines)
            if summary:
                deploy_update["failure_summary"] = sanitize(summary)

        await db.deployments.update_many(
            {"app_id": a["id"], "status": {"$in": ["queued", "building"]}},
            {"$set": deploy_update},
        )

    # 3) Backfill: any deployment that's already 'failed' but has no failure_summary
    # — pull logs from Coolify if possible. Handles two cases:
    #    (a) we already linked a coolify_deployment_uuid → fetch directly
    #    (b) we didn't link one → look up via the app's coolify_app_uuid
    backfill = await db.deployments.find(
        {
            "status": "failed",
            "$or": [
                {"failure_summary": None},
                {"failure_summary": {"$exists": False}},
                {"failure_summary": ""},
            ],
        },
        {"_id": 0, "id": 1, "app_id": 1, "coolify_deployment_uuid": 1, "logs": 1},
    ).sort("started_at", -1).limit(10).to_list(10)
    if not backfill:
        return

    import json as _json

    def _flatten_logs(raw):
        if isinstance(raw, str):
            try:
                raw = _json.loads(raw)
            except Exception:
                return [raw]
        out: list[str] = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    txt = item.get("output") or item.get("message") or ""
                    if txt:
                        out.append(str(txt).rstrip("\n"))
                elif isinstance(item, str):
                    out.append(item)
        return out

    for entry in backfill:
        cool_uuid = entry.get("coolify_deployment_uuid")
        if not cool_uuid:
            # Look up via app
            app = await db.apps.find_one({"id": entry["app_id"]})
            if not app or not app.get("coolify_app_uuid"):
                continue
            try:
                cool_deps = await coolify.list_deployments(app["coolify_app_uuid"])
            except Exception:
                continue
            if not cool_deps or not isinstance(cool_deps, list):
                continue
            head = cool_deps[0]
            if isinstance(head, dict):
                cool_uuid = head.get("deployment_uuid") or head.get("uuid")
        if not cool_uuid:
            continue
        try:
            full = await coolify.get_deployment(cool_uuid)
        except Exception:
            continue
        if not full:
            continue
        log_lines = _flatten_logs(full.get("logs"))
        if not log_lines:
            continue
        log_lines = sanitize_lines(log_lines)
        update = {"logs": log_lines, "coolify_deployment_uuid": cool_uuid}
        summary = extract_failure_summary(log_lines)
        if summary:
            update["failure_summary"] = sanitize(summary)
        await db.deployments.update_one({"id": entry["id"]}, {"$set": update})
