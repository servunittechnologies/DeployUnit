"""Central event dispatcher — the single, well-instrumented path every
platform event goes through to reach the user.

Why this exists
---------------
Before this module, SMS/email/Slack/Discord notifications only fired from
the "test" button on the Notifications page — the real platform events
(restart, deploy success/fail, app down/recovered, domain expiry, SSL
invalid) only wrote a row to the in-app `notifications` collection and
never reached the user's configured channels.

What dispatch_event() does
--------------------------
1. **Cooldown** — looks up `event_cooldowns` to drop duplicates within a
   configurable window (default 10 min per workspace+event+app).
2. **In-app bell** — writes ONE workspace-scoped row to `notifications`
   so the navbar bell always reflects the event regardless of channel
   preferences.
3. **External channels** — fans out to every workspace member that has
   the matching `event_type` in their `notification_prefs.channels.*`.
   Each member's send is independent: one user's missing phone number
   doesn't stop the others.
4. **Logging** — every external send is logged to `notification_sends`
   via send_alert, so the admin can audit delivery and refund credits
   on provider failures.

Cooldown collection schema (`event_cooldowns`):
    {workspace_id, event_type, app_id|None, last_at: ISO}
We use an upsert + $setOnInsert pattern so two concurrent ticks can't
both fire the same alert.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from pymongo.errors import DuplicateKeyError

from db import get_db
from services.notifications_sms import send_alert, SUPPORTED_EVENT_TYPES

logger = logging.getLogger(__name__)

# Default cooldown windows (seconds). Per event_type so noisy events like
# `app_down` debounce more aggressively than once-a-day events like
# `domain_expiring`.
COOLDOWN_DEFAULTS: dict[str, int] = {
    "app_down":         15 * 60,   # 15 min — uptime probe runs every 60s
    "app_recovered":    10 * 60,   # 10 min
    "deploy_failed":         60,   # 1 min — back-to-back deploys may fail; let each one ping once
    "deploy_succeeded":      60,
    "app_restarted":         30,
    "build_warning":     5 * 60,
    "domain_expiring":  6 * 3600,  # 6h — daily check
    "ssl_invalid":      6 * 3600,
    "credits_low":      6 * 3600,
}

# Map an event severity for the in-app bell row. The frontend renders these
# with colored dots — keep names aligned with the existing styles.
SEVERITY: dict[str, str] = {
    "app_down":        "error",
    "deploy_failed":   "error",
    "ssl_invalid":     "error",
    "build_warning":   "warning",
    "domain_expiring": "warning",
    "credits_low":     "warning",
    "app_recovered":   "info",
    "deploy_succeeded": "info",
    "app_restarted":   "info",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


async def _cooldown_passed(workspace_id: str, event_type: str, app_id: Optional[str], window_s: int) -> bool:
    """Atomically claim the cooldown slot for this (workspace, event, app).
    Returns True when we are the first caller within the window (i.e. we
    should fire), False when someone already fired recently.

    Relies on the unique index `event_cooldowns(workspace_id, event_type,
    app_id)` declared in db.py::ensure_indexes. The flow:
      1. Try to UPDATE an existing row only if its `last_at` is older than
         `cutoff`. If the row was stale we win and the update succeeds.
      2. If no stale row matched, INSERT a fresh one. The unique index
         either accepts it (no row existed → we win) or rejects it with
         DuplicateKeyError (a fresh row already exists → we lose).
    """
    db = get_db()
    now_iso = _now_iso()
    cutoff = (_now() - timedelta(seconds=window_s)).isoformat()
    key = {
        "workspace_id": workspace_id,
        "event_type": event_type,
        "app_id": app_id,
    }
    # 1) Refresh a stale row in place.
    res = await db.event_cooldowns.update_one(
        {**key, "last_at": {"$lt": cutoff}},
        {"$set": {"last_at": now_iso}},
        upsert=False,
    )
    if res.matched_count:
        return True
    # 2) No stale row → try to insert a brand new claim. Unique index
    #    prevents two concurrent dispatchers from both succeeding.
    try:
        await db.event_cooldowns.insert_one({**key, "last_at": now_iso})
        return True
    except DuplicateKeyError:
        return False


async def _write_inapp_notification(
    *,
    workspace_id: str,
    event_type: str,
    title: str,
    message: str,
    severity: str,
    app_id: Optional[str],
    link: Optional[str],
) -> None:
    db = get_db()
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "workspace_id": workspace_id,
        "user_id": None,
        "type": event_type,
        "event_type": event_type,
        "title": title,
        "message": message,
        "severity": severity,
        "read": False,
        "link": link or (f"/app/apps/{app_id}" if app_id else None),
        "app_id": app_id,
        "created_at": _now_iso(),
    })


async def _members_with_prefs(workspace_id: str) -> list[dict]:
    """Every member of the workspace whose notification_prefs has at least
    one channel populated. Includes the owner (workspaces.owner_id) AND
    any rows in workspace_members."""
    db = get_db()
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0, "owner_id": 1})
    member_ids: set[str] = set()
    if ws and ws.get("owner_id"):
        member_ids.add(ws["owner_id"])
    async for m in db.workspace_members.find({"workspace_id": workspace_id}, {"_id": 0, "user_id": 1}):
        if m.get("user_id"):
            member_ids.add(m["user_id"])
    if not member_ids:
        return []
    users = await db.users.find(
        {"id": {"$in": list(member_ids)}},
        {"_id": 0},
    ).to_list(50)
    # Filter to users with at least one channel preference configured.
    return [u for u in users if (u.get("notification_prefs") or {}).get("channels")]


async def dispatch_event(
    *,
    workspace_id: str,
    event_type: str,
    title: str,
    body: str,
    app_id: Optional[str] = None,
    link: Optional[str] = None,
    cooldown_seconds: Optional[int] = None,
    force: bool = False,
) -> dict:
    """Fan out a platform event to every channel the user has opted in to.

    Always writes the in-app notification (so the bell reflects reality).
    Honors per-event cooldown unless `force=True` (used by manual admin
    triggers and the test endpoint).

    Returns a summary dict for logging — never raises so a noisy event
    can't crash the caller (deployment sync, monitor tick, etc).
    """
    try:
        if event_type not in SUPPORTED_EVENT_TYPES:
            logger.warning("dispatch_event: unsupported event_type=%s — adding to bell only", event_type)

        window = cooldown_seconds if cooldown_seconds is not None else COOLDOWN_DEFAULTS.get(event_type, 600)
        if not force and window > 0:
            if not await _cooldown_passed(workspace_id, event_type, app_id, window):
                return {"skipped": "cooldown", "event": event_type}

        severity = SEVERITY.get(event_type, "info")
        await _write_inapp_notification(
            workspace_id=workspace_id, event_type=event_type,
            title=title, message=body, severity=severity,
            app_id=app_id, link=link,
        )

        # External channels — per workspace member.
        members = await _members_with_prefs(workspace_id)
        results = []
        for u in members:
            try:
                r = await send_alert(
                    workspace_id=workspace_id,
                    user=u,
                    event_type=event_type,
                    title=title,
                    body=body,
                )
                results.append({"user_id": u["id"], "results": r})
            except Exception as e:
                logger.exception("dispatch_event: send_alert raised for user=%s event=%s: %s",
                                 u.get("id"), event_type, e)
                results.append({"user_id": u["id"], "error": str(e)[:200]})
        return {"event": event_type, "members": len(members), "results": results}
    except Exception as e:
        # Last-resort safety net so a notification failure never breaks a
        # critical platform flow (deploy, restart, monitor).
        logger.exception("dispatch_event failed for event=%s: %s", event_type, e)
        return {"error": str(e)[:200], "event": event_type}
