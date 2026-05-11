"""Plan price-change grandfathering.

When an admin raises a plan's price, existing paid subscriptions on that
plan are "grandfathered" — they keep paying the old price for a configurable
window (default 180 days) before the new price kicks in. EU consumer law
also typically requires at least 30 days notice for price changes.

Storage:
  subscriptions.{
    grandfathered_price: float | null,   # the old price this sub keeps paying
    grandfathered_until: ISO | null,     # after this date, new price applies
    notified_at: ISO | null              # when we sent the heads-up notification
  }

Public surface:
  - apply_price_change(plan_id, old_price, new_price, notice_days=180)
      → snapshot all active subs at the old price for `notice_days`
  - effective_price(workspace_id, plan) → float
      → returns old grandfathered price if still valid, else the current plan price
  - upcoming_change(workspace_id, plan) → dict|None
      → describes when the price changes (for the banner in /billing)
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import get_db

logger = logging.getLogger(__name__)


DEFAULT_NOTICE_DAYS = 180


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def apply_price_change(
    plan_id: str,
    old_price: float,
    new_price: float,
    *,
    notice_days: int = DEFAULT_NOTICE_DAYS,
) -> int:
    """Snapshot active subscriptions on `plan_id` to the old price for
    `notice_days`. Only applies to PRICE INCREASES — drops are passed on
    immediately. Returns # of subs grandfathered. Idempotent: re-running
    won't shorten an already-granted grandfather period.
    """
    if new_price <= old_price:
        return 0
    db = get_db()
    until = _iso(_now() + timedelta(days=notice_days))
    # Only affect ACTIVE subs on the plan. Skip subs that already have a
    # grandfather window extending further than what we'd grant.
    res = await db.subscriptions.update_many(
        {
            "plan": plan_id,
            "status": "active",
            "$or": [
                {"grandfathered_until": None},
                {"grandfathered_until": {"$exists": False}},
                {"grandfathered_until": {"$lt": until}},
            ],
        },
        {
            "$set": {
                "grandfathered_price": old_price,
                "grandfathered_until": until,
            },
        },
    )
    if res.modified_count:
        logger.info(
            "grandfathering: %s subs on plan=%s locked to €%.2f until %s",
            res.modified_count, plan_id, old_price, until,
        )
    # Audit log for admin visibility
    await db.price_change_log.insert_one({
        "id": str(uuid.uuid4()),
        "plan_id": plan_id,
        "old_price": old_price,
        "new_price": new_price,
        "notice_days": notice_days,
        "effective_until": until,
        "subs_affected": int(res.modified_count or 0),
        "created_at": _iso(_now()),
    })
    return int(res.modified_count or 0)


async def effective_price(workspace_id: str, plan: dict) -> float:
    """Resolve what THIS workspace actually pays right now on the given plan.
    Honors grandfathering if the window is still open."""
    db = get_db()
    sub = await db.subscriptions.find_one(
        {"workspace_id": workspace_id, "plan": plan["id"]},
        {"_id": 0, "grandfathered_price": 1, "grandfathered_until": 1},
    )
    if not sub:
        return float(plan.get("price") or 0)
    locked = sub.get("grandfathered_price")
    until = sub.get("grandfathered_until")
    if locked is None or not until:
        return float(plan.get("price") or 0)
    try:
        end = datetime.fromisoformat(str(until).replace("Z", "+00:00"))
    except Exception:
        return float(plan.get("price") or 0)
    if end > _now():
        return float(locked)
    return float(plan.get("price") or 0)


async def upcoming_change(workspace_id: str, plan: dict) -> Optional[dict]:
    """If this workspace has a pending price change, describe it so the UI
    can render a banner. Returns None if no grandfather window is active."""
    db = get_db()
    sub = await db.subscriptions.find_one(
        {"workspace_id": workspace_id, "plan": plan["id"], "status": "active"},
        {"_id": 0, "grandfathered_price": 1, "grandfathered_until": 1},
    )
    if not sub:
        return None
    locked = sub.get("grandfathered_price")
    until = sub.get("grandfathered_until")
    if locked is None or not until:
        return None
    try:
        end = datetime.fromisoformat(str(until).replace("Z", "+00:00"))
    except Exception:
        return None
    if end <= _now():
        return None
    return {
        "current_price": float(locked),
        "new_price": float(plan.get("price") or 0),
        "effective_at": until,
        "days_remaining": max(0, (end - _now()).days),
    }
