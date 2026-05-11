"""Run + persist Google PageSpeed audits per app."""
import uuid
import logging
from datetime import datetime, timezone, timedelta

from db import get_db
from clients.pagespeed import run_audit, configured

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def run_for_app(app_id: str, *, manual: bool = False) -> dict:
    """Run mobile + desktop audits against an app's primary_url, persist, return both."""
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0, "id": 1, "workspace_id": 1, "primary_url": 1, "name": 1})
    if not app:
        return {"ok": False, "error": "app not found"}
    url = (app.get("primary_url") or "").strip()
    if not url:
        return {"ok": False, "error": "app has no primary URL yet"}
    if not configured():
        return {"ok": False, "error": "PageSpeed not configured on this platform"}

    mobile = await run_audit(url, strategy="mobile")
    desktop = await run_audit(url, strategy="desktop")

    doc = {
        "id": str(uuid.uuid4()),
        "app_id": app["id"],
        "workspace_id": app.get("workspace_id"),
        "url": url,
        "ran_at": _now().isoformat(),
        "manual": manual,
        "mobile": mobile,
        "desktop": desktop,
    }
    await db.pagespeed_runs.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "run": doc}


async def latest_for_app(app_id: str) -> dict | None:
    db = get_db()
    return await db.pagespeed_runs.find_one(
        {"app_id": app_id},
        {"_id": 0},
        sort=[("ran_at", -1)],
    )


async def history_for_app(app_id: str, *, days: int = 30) -> list[dict]:
    db = get_db()
    since = (_now() - timedelta(days=days)).isoformat()
    cur = db.pagespeed_runs.find(
        {"app_id": app_id, "ran_at": {"$gte": since}},
        {"_id": 0, "ran_at": 1, "mobile.scores": 1, "desktop.scores": 1,
         "mobile.lab_metrics": 1, "desktop.lab_metrics": 1},
    ).sort("ran_at", 1)
    return await cur.to_list(500)


async def daily_pagespeed_tick() -> dict:
    """APScheduler job: for every app with a primary_url that hasn't been
    audited in 24h, run a fresh audit. Skips apps on plans without the
    pagespeed feature.
    """
    db = get_db()
    if not configured():
        return {"ran": 0, "skipped": 0, "reason": "no api key"}
    since = (_now() - timedelta(hours=24)).isoformat()
    apps = await db.apps.find({"primary_url": {"$exists": True, "$ne": None}},
                              {"_id": 0, "id": 1, "workspace_id": 1, "primary_url": 1}).to_list(500)
    from services.plans import get_plan
    ran, skipped = 0, 0
    for app in apps:
        ws = await db.workspaces.find_one({"id": app.get("workspace_id")},
                                          {"_id": 0, "owner_id": 1})
        owner = await db.users.find_one({"id": (ws or {}).get("owner_id")},
                                        {"_id": 0, "plan": 1}) if ws else None
        plan_id = (owner or {}).get("plan", "free")
        plan = await get_plan(plan_id)
        if not (plan or {}).get("features_block", {}).get("pagespeed", False):
            skipped += 1
            continue
        last = await db.pagespeed_runs.find_one(
            {"app_id": app["id"], "ran_at": {"$gte": since}},
            {"_id": 0, "id": 1},
        )
        if last:
            skipped += 1
            continue
        try:
            await run_for_app(app["id"], manual=False)
            ran += 1
        except Exception as e:
            logger.exception("daily pagespeed for %s: %s", app["id"], e)
    return {"ran": ran, "skipped": skipped}
