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
from services.log_parser import extract_failure_summary, classify_failure
from services.whitelabel import sanitize, sanitize_lines

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _evaluate_alerts(app: dict, ok: bool, response_ms: int | None):
    """Apply alert rules for an app result + dispatch app_down/app_recovered
    notifications when the state actually flips. Cooldown is owned by the
    central dispatcher so SMS / email / slack / discord don't get spammed
    every minute the app stays down."""
    db = get_db()
    # Track the previous state so we know when we *transition* (down→up or
    # up→down). Without this we'd never fire `app_recovered`.
    prev_ok = app.get("monitor_last_ok")
    state_changed = (prev_ok is None) or (bool(prev_ok) != bool(ok))
    await db.apps.update_one(
        {"id": app["id"]},
        {"$set": {"monitor_last_ok": bool(ok), "monitor_last_checked_at": _now_iso()}},
    )

    if state_changed:
        from services.event_dispatcher import dispatch_event
        if not ok:
            await dispatch_event(
                workspace_id=app["workspace_id"],
                event_type="app_down",
                title=f"{app['name']} is DOWN",
                body=f"{app.get('primary_url') or app['name']} stopped responding.",
                app_id=app["id"],
            )
        elif prev_ok is False:
            # Only fire `recovered` when we actually transitioned from down
            # to up — not for the very first probe of a freshly seen app.
            await dispatch_event(
                workspace_id=app["workspace_id"],
                event_type="app_recovered",
                title=f"{app['name']} is back",
                body=f"{app.get('primary_url') or app['name']} is responding again.",
                app_id=app["id"],
            )

    # Legacy `alert_rules` path — kept for the "slow response" threshold
    # rule which has no dispatcher equivalent yet.
    rules = await db.alert_rules.find(
        {"workspace_id": app["workspace_id"], "enabled": True,
         "$or": [{"app_id": app["id"]}, {"app_id": None}]},
        {"_id": 0},
    ).to_list(50)
    for rule in rules:
        if rule["type"] != "slow_response":
            continue
        if not (response_ms and rule.get("threshold") and response_ms > rule["threshold"]):
            continue
        last = rule.get("last_triggered_at")
        if last:
            last_dt = datetime.fromisoformat(last) if isinstance(last, str) else last
            if (datetime.now(timezone.utc) - last_dt).total_seconds() < rule.get("cooldown_seconds", 600):
                continue
        await db.alert_rules.update_one(
            {"id": rule["id"]}, {"$set": {"last_triggered_at": _now_iso()}}
        )
        from services.event_dispatcher import dispatch_event
        await dispatch_event(
            workspace_id=app["workspace_id"],
            event_type="build_warning",
            title=f"{app['name']} responding slowly",
            body=f"Response time {response_ms}ms exceeds threshold {rule['threshold']}ms.",
            app_id=app["id"],
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


async def _retry_transient_deployment(db, app: dict) -> None:
    """Re-trigger the most recent failed deployment when the failure was a
    known build-engine race condition (Docker 'No such container', network
    cleanup glitches, etc).

    Strategy: call `coolify.stop()` first so the build engine drops any stale
    helper-container references, wait a few seconds, then deploy(force=True).
    Capped at 1 auto-retry per row to prevent loops.
    """
    failed = await db.deployments.find_one(
        {"app_id": app["id"], "status": "failed"},
        {"_id": 0, "id": 1, "auto_retry_count": 1},
        sort=[("started_at", -1)],
    )
    if not failed:
        return
    if int(failed.get("auto_retry_count") or 0) >= 1:
        # Already retried once — don't loop. Surface the failure for real.
        return
    coolify_uuid = app.get("coolify_app_uuid")
    if not coolify_uuid:
        return
    logger.info(
        "auto-retry: transient failure on app=%s deployment=%s — clearing build-engine state then redeploying",
        app["id"], failed["id"],
    )
    await db.deployments.update_one(
        {"id": failed["id"]},
        {
            "$set": {"status": "building", "finished_at": None, "failure_transient": True},
            "$inc": {"auto_retry_count": 1},
            "$push": {"logs": "[AUTO-RETRY] clearing stale build-engine state…"},
        },
    )
    try:
        # Step 1 — Stop the app so the build engine releases any stale
        # helper-container UUID it had cached for this resource.
        await coolify.stop(coolify_uuid)
        # Step 2 — Give it ~3s to fully tear down and update its internal state.
        await asyncio.sleep(3)
        # Step 3 — Force a clean redeploy. force=true tells Coolify to skip
        # any "already running" short-circuits and rebuild from scratch.
        await db.deployments.update_one(
            {"id": failed["id"]},
            {"$push": {"logs": "[AUTO-RETRY] retriggering deploy from clean state"}},
        )
        res = await coolify.deploy(coolify_uuid, force=True)
        new_uuid = (res or {}).get("deployment_uuid") or (res or {}).get("uuid")
        if new_uuid:
            await db.deployments.update_one(
                {"id": failed["id"]},
                {"$set": {"coolify_deployment_uuid": new_uuid}},
            )
    except Exception as e:
        logger.warning("auto-retry failed for app=%s: %s", app["id"], e)
        await db.deployments.update_one(
            {"id": failed["id"]},
            {"$set": {"status": "failed",
                      "failure_summary": f"Auto-retry failed: {str(e)[:160]}"},
             "$push": {"logs": f"[AUTO-RETRY] failed: {e}"}},
        )




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
        # Legacy cleanup: rewrite any stored sslip URLs on every sync so the
        # platform never exposes the build-engine fallback domain.
        legacy = a.get("primary_url") or ""
        legacy_cleanup = {}
        if "sslip.io" in legacy:
            if a.get("cloudflare_fqdn"):
                legacy_cleanup["primary_url"] = f"https://{a['cloudflare_fqdn']}"
            else:
                legacy_cleanup["primary_url"] = None
        # No state change → still flush legacy cleanup if needed, then skip.
        if new_status == a.get("status"):
            if legacy_cleanup:
                await db.apps.update_one({"id": a["id"]}, {"$set": legacy_cleanup})
            continue
        # Build a candidate primary_url from whatever Coolify returns, then
        # only accept it if it isn't the sslip catch-all (we never want to
        # surface that to end-users) AND the app doesn't already have a
        # Cloudflare-issued FQDN (which is always the source of truth).
        fqdn = info.get("fqdn") or info.get("preview_fqdn")
        primary_url = None
        if fqdn:
            candidate = fqdn if fqdn.startswith("http") else f"https://{fqdn.split(',')[0]}"
            if "sslip.io" not in candidate and not a.get("cloudflare_fqdn"):
                primary_url = candidate
        update = {"status": new_status, **legacy_cleanup}
        if primary_url and "primary_url" not in update:
            update["primary_url"] = primary_url
        if new_status in ("live", "failed"):
            update["last_deploy_at"] = _now_iso()
        await db.apps.update_one({"id": a["id"]}, {"$set": update})

        # Fire deploy_succeeded / deploy_failed when we just learned of a
        # terminal state transition. We only dispatch when status actually
        # flipped (handled by `if new_status == a.get("status"): continue`
        # earlier) — so this only runs on real state changes.
        try:
            from services.event_dispatcher import dispatch_event
            if new_status == "live":
                # Was building/queued/failed → now live = success.
                await dispatch_event(
                    workspace_id=a["workspace_id"],
                    event_type="deploy_succeeded",
                    title=f"{a.get('name') or a['id']} deployed successfully",
                    body=f"Latest build is live at {primary_url or a.get('primary_url') or '—'}",
                    app_id=a["id"],
                )
            elif new_status == "failed":
                await dispatch_event(
                    workspace_id=a["workspace_id"],
                    event_type="deploy_failed",
                    title=f"{a.get('name') or a['id']} deploy failed",
                    body="The latest build did not finish — check the Deployments tab for the failure log.",
                    app_id=a["id"],
                )
        except Exception as e:
            logger.warning("dispatch deploy event failed for %s: %s", a.get("id"), e)
        # Safety net: every app that goes live without a managed Cloudflare
        # subdomain gets one auto-provisioned now. Random 8-char prefix so
        # branded names never leak into public DNS history. Runs once per
        # app — provision_subdomain is a no-op when Cloudflare isn't
        # configured, and we only enter this branch when cloudflare_fqdn is
        # still unset.
        if new_status == "live" and not a.get("cloudflare_fqdn"):
            try:
                from services.subdomains import provision_subdomain
                sub = await provision_subdomain({**a, **update})
                if sub:
                    await db.apps.update_one(
                        {"id": a["id"]},
                        {"$set": {
                            "primary_url": sub["primary_url"],
                            "cloudflare_dns_record_id": sub["record_id"],
                            "cloudflare_fqdn": sub["fqdn"],
                            "cloudflare_slug": sub.get("cf_slug"),
                        }},
                    )
                    try:
                        await coolify.update_application(
                            a["coolify_app_uuid"],
                            {"fqdn": f"https://{sub['fqdn']}"},
                        )
                    except Exception as e:
                        logger.warning("coolify fqdn sync after auto-provision failed for %s: %s", a["id"], e)
            except Exception as e:
                logger.warning("auto-provision subdomain failed for %s: %s", a["id"], e)
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
            cls = classify_failure(cool_log_lines)
            if cls["summary"]:
                deploy_update["failure_summary"] = sanitize(cls["summary"])
            deploy_update["failure_transient"] = cls["transient"]

        await db.deployments.update_many(
            {"app_id": a["id"], "status": {"$in": ["queued", "building"]}},
            {"$set": deploy_update},
        )

        # Auto-retry transient build-engine glitches — bounded to 1 retry per
        # deployment row to prevent loops. Picks up the current failed row(s)
        # and re-triggers Coolify silently. The user just sees a brief "failed"
        # blip followed by a new "building" record.
        if new_status == "failed" and deploy_update.get("failure_transient"):
            await _retry_transient_deployment(db, a)

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
                # No way to ever recover logs for this row — stamp it so the
                # watchdog stops re-querying the build engine forever.
                await db.deployments.update_one(
                    {"id": entry["id"]},
                    {"$set": {"failure_summary": "build engine no longer has logs for this deployment"}},
                )
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
            # 404 from build engine — deployment is gone. Stamp a placeholder
            # so this row drops out of the backfill query and we stop spamming.
            await db.deployments.update_one(
                {"id": entry["id"]},
                {"$set": {"failure_summary": "build engine no longer has logs for this deployment"}},
            )
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



async def status_sampler():
    """Record a status snapshot for every app so we can render a healthy/down
    timeline in the analytics tab. Runs every 5 minutes.

    The snapshot rows live in `app_status_samples` and are tiny:
        {id, app_id, workspace_id, status, sampled_at}
    """
    db = get_db()
    now_iso = _now_iso()
    cur = db.apps.find({}, {"_id": 0, "id": 1, "workspace_id": 1, "status": 1})
    docs = []
    async for a in cur:
        docs.append({
            "id": str(uuid.uuid4()),
            "app_id": a["id"],
            "workspace_id": a.get("workspace_id"),
            "status": a.get("status") or "unknown",
            "sampled_at": now_iso,
        })
    if docs:
        await db.app_status_samples.insert_many(docs)
    # Garbage-collect anything older than 31 days so the collection doesn't
    # grow unbounded.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    await db.app_status_samples.delete_many({"sampled_at": {"$lt": cutoff}})
