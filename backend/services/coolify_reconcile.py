"""Coolify ↔ DeployUnit drift reconciler.

Runs every 10 min in the background:

* Pulls the full list of Coolify applications.
* Marks any DeployUnit app whose `coolify_app_uuid` is gone from Coolify as
  `status='archived'` (NOT hard-deleted — admin can still inspect history,
  see logs, etc).
* Tallies how many Coolify apps DON'T have a DeployUnit record at all so the
  Metrics agent UI can show a compact "N unmanaged Coolify resources" pill —
  pure info, no warning spam, no per-UUID actions. Performant 1-to-1 mapping.

Public entrypoints:
  * reconcile_tick()       → {checked, archived, unmanaged} — scheduler tick
  * unmanaged_count_cached → reads the count without a Coolify round-trip
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from clients.coolify import coolify
from db import get_db

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def reconcile_tick() -> dict:
    db = get_db()
    try:
        coolify_apps = await coolify.list_applications()
    except Exception as e:
        logger.warning("reconcile: list_applications failed: %s", e)
        return {"checked": 0, "archived": 0, "unmanaged": None, "error": str(e)[:120]}

    coolify_uuids = {a.get("uuid") for a in coolify_apps if a.get("uuid")}

    # 1) Archive DeployUnit apps that no longer exist on the build engine.
    archived = 0
    cursor = db.apps.find(
        {
            "coolify_app_uuid": {"$ne": None, "$exists": True},
            "status": {"$nin": ["archived", "deleted"]},
        },
        {"_id": 0, "id": 1, "coolify_app_uuid": 1, "name": 1},
    )
    async for app in cursor:
        if app["coolify_app_uuid"] not in coolify_uuids:
            await db.apps.update_one(
                {"id": app["id"]},
                {"$set": {
                    "status": "archived",
                    "archived_at": _now(),
                    "archived_reason": "no longer on build engine",
                }},
            )
            archived += 1
            logger.info("reconcile: archived app %s (%s) — gone from Coolify",
                        app["id"], app.get("name"))

    # 2) Count Coolify apps that DeployUnit doesn't know about. Pure info —
    # we do NOT auto-import (we don't know which workspace they should land in).
    deployunit_uuids = {a["coolify_app_uuid"] async for a in db.apps.find(
        {"coolify_app_uuid": {"$ne": None}}, {"_id": 0, "coolify_app_uuid": 1}
    )}
    unmanaged = len(coolify_uuids - deployunit_uuids)

    # Cache the count so the agent endpoint can show it without re-fetching
    # the whole Coolify app list every 30s.
    await db.platform_settings.update_one(
        {"id": "platform-singleton"},
        {"$set": {
            "metrics_agent.unmanaged_coolify_count": unmanaged,
            "metrics_agent.last_reconcile_at": _now(),
        }},
        upsert=True,
    )

    return {
        "checked": len(coolify_uuids),
        "archived": archived,
        "unmanaged": unmanaged,
    }


async def unmanaged_count_cached() -> int:
    """Cheap read of the cached count for the agent endpoint."""
    db = get_db()
    doc = await db.platform_settings.find_one(
        {"id": "platform-singleton"},
        {"_id": 0, "metrics_agent.unmanaged_coolify_count": 1},
    ) or {}
    return int(((doc.get("metrics_agent") or {}).get("unmanaged_coolify_count")) or 0)
