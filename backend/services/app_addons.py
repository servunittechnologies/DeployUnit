"""Generic per-app paid add-on subscription manager.

One module, one collection (`app_addon_subscriptions`), every paid feature
that's billed per-app/per-month plugs in here. New add-ons just add an
entry to `ADDON_CATALOG` and write the consumer-side check
(`is_active(app_id, addon_id)`).

State machine
-------------
        enable_addon ── charges first month ── creates row
                              │
                              ▼
                       ┌─────────────┐
                       │   active    │  expires_at = +30d
                       └──────┬──────┘
            scheduler tick    │  expires_at < now
                              ▼
                  ┌────────────────────────┐
                  │ try to charge          │
                  └────────┬─────┬─────────┘
                       ok  │     │  no balance
                           ▼     ▼
                    active (+30d)   grace (7d) ──► expired
                                                       ▲
              user cancel ─────► cancelled ────────────┘
                                  (active until expires_at)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException

from db import get_db
from services.credits import consume_credits, get_balance

logger = logging.getLogger(__name__)


# Catalog — keep this in sync with the public pricing page. Costs in
# credits/month. `display_name` shows in audit logs + admin UI.
ADDON_CATALOG: dict[str, dict] = {
    "log-retention": {
        "display_name": "Extended log retention",
        "cost_cr_month": 100,
        "description": "Keep metrics & uptime samples for 30 days instead of 7.",
    },
    "heatmaps": {
        "display_name": "Site heatmaps",
        "cost_cr_month": 100,
        "description": "Click/scroll heatmaps per page · in-house collector, no 3rd party scripts.",
    },
    "static-ip": {
        "display_name": "Reserved static IP",
        "cost_cr_month": 50,
        "description": "Pin your app to a fixed IP for whitelists / 3rd party integrations.",
    },
}

# How long a billing period is. Used both for `expires_at` math and for the
# pro-rata refund computation on early cancellation.
PERIOD_DAYS = 30
GRACE_DAYS = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _addon_or_404(addon_id: str) -> dict:
    if addon_id not in ADDON_CATALOG:
        raise HTTPException(status_code=404, detail=f"Unknown add-on '{addon_id}'.")
    return ADDON_CATALOG[addon_id]


async def get_subscription(app_id: str, addon_id: str) -> Optional[dict]:
    db = get_db()
    return await db.app_addon_subscriptions.find_one(
        {"app_id": app_id, "addon_id": addon_id},
        {"_id": 0},
    )


async def is_active(app_id: str, addon_id: str) -> bool:
    """The single hot-path read used by feature code (log GC, heatmap
    collector, etc). Returns True if the app is currently entitled,
    including during a grace period."""
    sub = await get_subscription(app_id, addon_id)
    if not sub:
        return False
    return sub.get("status") in ("active", "grace", "cancelled") and sub.get("expires_at", "") > _now_iso()


async def active_app_ids(addon_id: str) -> set[str]:
    """Bulk version of `is_active` — gives all app_ids currently entitled
    to `addon_id`. Used by retention GC and other batch jobs."""
    db = get_db()
    cur = db.app_addon_subscriptions.find(
        {
            "addon_id": addon_id,
            "status": {"$in": ["active", "grace", "cancelled"]},
            "expires_at": {"$gt": _now_iso()},
        },
        {"_id": 0, "app_id": 1},
    )
    return {row["app_id"] async for row in cur}


async def list_for_app(app_id: str) -> list[dict]:
    db = get_db()
    rows = await db.app_addon_subscriptions.find(
        {"app_id": app_id}, {"_id": 0},
    ).to_list(50)
    # Enrich with catalog data
    out = []
    for r in rows:
        cat = ADDON_CATALOG.get(r["addon_id"]) or {}
        out.append({**r, "display_name": cat.get("display_name", r["addon_id"]),
                    "description": cat.get("description", ""),
                    "cost_cr_month": cat.get("cost_cr_month", r.get("cost_cr_month", 0))})
    return out


async def enable_addon(app: dict, addon_id: str, actor_user_id: Optional[str] = None) -> dict:
    """Charge the first month and create / re-activate a subscription.
    Returns the subscription dict ready for the UI."""
    db = get_db()
    cat = _addon_or_404(addon_id)
    cost = int(cat["cost_cr_month"])
    workspace_id = app["workspace_id"]
    app_id = app["id"]

    existing = await get_subscription(app_id, addon_id)
    if existing and existing.get("status") == "active" and existing.get("expires_at", "") > _now_iso():
        return existing  # idempotent — already on

    # Charge first month synchronously — caller surfaces 402 to the UI.
    await consume_credits(
        workspace_id, cost,
        reason=f"addon '{addon_id}' for app {app.get('name') or app_id}",
        ref_id=app_id,
        ref_type="app_addon",
        user_id=actor_user_id,
    )

    now_iso = _now_iso()
    expires_at = (_now() + timedelta(days=PERIOD_DAYS)).isoformat()
    sub = {
        "id": existing["id"] if existing else str(uuid.uuid4()),
        "app_id": app_id,
        "workspace_id": workspace_id,
        "addon_id": addon_id,
        "cost_cr_month": cost,
        "status": "active",
        "started_at": existing.get("started_at") if existing else now_iso,
        "expires_at": expires_at,
        "last_charge_at": now_iso,
        "last_charge_cr": cost,
        "grace_started_at": None,
        "cancelled_at": None,
    }
    await db.app_addon_subscriptions.update_one(
        {"app_id": app_id, "addon_id": addon_id},
        {"$set": sub}, upsert=True,
    )
    logger.info("addon enabled: app=%s addon=%s cost=%d", app_id, addon_id, cost)
    return sub


async def cancel_addon(app_id: str, addon_id: str) -> dict:
    """Mark for non-renewal. The user keeps access until `expires_at`."""
    db = get_db()
    existing = await get_subscription(app_id, addon_id)
    if not existing:
        return {"status": "none"}
    if existing.get("status") in ("expired", "cancelled"):
        return existing
    await db.app_addon_subscriptions.update_one(
        {"app_id": app_id, "addon_id": addon_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": _now_iso(),
        }},
    )
    return await get_subscription(app_id, addon_id)


async def renew_tick() -> dict:
    """Scheduler entrypoint. Iterates every subscription whose `expires_at`
    has passed and either renews it (active → charge → +30d) or downgrades
    it (grace expires → expired, cancelled → expired)."""
    db = get_db()
    now = _now()
    now_iso = now.isoformat()
    renewed = 0
    grace = 0
    expired = 0
    cur = db.app_addon_subscriptions.find(
        {"expires_at": {"$lte": now_iso},
         "status": {"$in": ["active", "grace", "cancelled"]}},
        {"_id": 0},
    )
    async for sub in cur:
        status = sub["status"]
        app_id = sub["app_id"]
        addon_id = sub["addon_id"]
        workspace_id = sub["workspace_id"]
        cost = int(sub["cost_cr_month"])

        if status == "cancelled":
            await db.app_addon_subscriptions.update_one(
                {"app_id": app_id, "addon_id": addon_id},
                {"$set": {"status": "expired", "expired_at": now_iso}},
            )
            expired += 1
            continue

        if status == "grace":
            grace_started = sub.get("grace_started_at")
            if grace_started:
                try:
                    gs = datetime.fromisoformat(grace_started)
                    if (now - gs).days >= GRACE_DAYS:
                        await db.app_addon_subscriptions.update_one(
                            {"app_id": app_id, "addon_id": addon_id},
                            {"$set": {"status": "expired", "expired_at": now_iso}},
                        )
                        expired += 1
                        continue
                except (ValueError, TypeError):
                    pass
            # otherwise fall through and retry charge (recovered balance?)

        # Try to charge
        try:
            await consume_credits(
                workspace_id, cost,
                reason=f"addon '{addon_id}' renewal",
                ref_id=app_id,
                ref_type="app_addon",
            )
            await db.app_addon_subscriptions.update_one(
                {"app_id": app_id, "addon_id": addon_id},
                {"$set": {
                    "status": "active",
                    "expires_at": (now + timedelta(days=PERIOD_DAYS)).isoformat(),
                    "last_charge_at": now_iso,
                    "last_charge_cr": cost,
                    "grace_started_at": None,
                }},
            )
            renewed += 1
        except HTTPException as e:
            # 402 = insufficient credits → enter grace
            if e.status_code != 402:
                logger.warning("renew charge unexpected error: %s", e.detail)
                continue
            await db.app_addon_subscriptions.update_one(
                {"app_id": app_id, "addon_id": addon_id},
                {"$set": {
                    "status": "grace",
                    "grace_started_at": sub.get("grace_started_at") or now_iso,
                    "expires_at": (now + timedelta(days=1)).isoformat(),  # re-check tomorrow
                }},
            )
            # Notify the workspace once
            try:
                from services.event_dispatcher import dispatch_event
                await dispatch_event(
                    workspace_id=workspace_id,
                    event_type="credits_low",
                    title="Add-on renewal failed — top up needed",
                    body=f"Could not renew {ADDON_CATALOG.get(addon_id,{}).get('display_name', addon_id)} on app {app_id}: insufficient credits. You have {GRACE_DAYS} days to top up before the feature is disabled.",
                    app_id=app_id,
                )
            except Exception as ex:
                logger.warning("addon grace notification failed: %s", ex)
            grace += 1
    if renewed or grace or expired:
        logger.info("addon renew tick: renewed=%d grace=%d expired=%d", renewed, grace, expired)
    return {"renewed": renewed, "grace": grace, "expired": expired,
            "ran_at": now_iso}
