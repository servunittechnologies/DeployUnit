"""One-shot migration: move plan + credits + billing-profile from
`workspaces` documents to their owner `users` documents.

Rules:
  * Plan: highest plan across all workspaces the user owns wins.
    (free < pro < agency)
  * Credits balance: sum of all workspace.credits_balance for that user.
  * Credit period: earliest credits_period_start across owned workspaces.
  * Billing profile: pick the workspace billing profile that's most recently
    updated; copy to user.billing_profile (also keep on workspace for old
    callers until they are refactored).

Runs on server startup if `users.plan` is missing for ANY user. Idempotent —
safe to run multiple times; users already migrated are skipped.
"""
import logging
from datetime import datetime, timezone

from db import get_db

logger = logging.getLogger(__name__)


PLAN_RANK = {"free": 0, "hobby": 0, "pro": 1, "agency": 2}


def _rank(plan_id: str) -> int:
    return PLAN_RANK.get(plan_id or "free", 0)


async def migrate_accounts(force: bool = False) -> dict:
    """Returns a small dict describing what got moved (for log + admin view)."""
    db = get_db()
    moved = 0
    skipped = 0
    users = db.users.find({}, {"_id": 0})
    async for u in users:
        if not force and u.get("plan") is not None and u.get("credits_balance") is not None:
            skipped += 1
            continue
        owned = await db.workspaces.find(
            {"owner_id": u["id"]},
            {"_id": 0, "id": 1, "plan": 1, "credits_balance": 1,
             "credits_period_start": 1, "credits_granted_total": 1,
             "plan_changed_at": 1},
        ).to_list(200)
        # Best plan
        best_plan = "free"
        best_rank = -1
        plan_changed_at = None
        credits_total = 0
        granted_total = 0
        earliest_period = None
        for w in owned:
            r = _rank(w.get("plan") or "free")
            if r > best_rank:
                best_rank = r
                best_plan = (w.get("plan") or "free")
                plan_changed_at = w.get("plan_changed_at")
            credits_total += int(w.get("credits_balance") or 0)
            granted_total += int(w.get("credits_granted_total") or 0)
            ps = w.get("credits_period_start")
            if ps and (earliest_period is None or ps < earliest_period):
                earliest_period = ps
        # Pick the most recently-updated billing profile
        wid_list = [w["id"] for w in owned]
        billing_profile = None
        if wid_list:
            billing_profile = await db.billing_profiles.find_one(
                {"workspace_id": {"$in": wid_list}},
                {"_id": 0},
                sort=[("updated_at", -1)],
            )
        update = {
            "plan": best_plan,
            "credits_balance": credits_total,
            "credits_granted_total": granted_total,
        }
        if plan_changed_at:
            update["plan_changed_at"] = plan_changed_at
        if earliest_period:
            update["credits_period_start"] = earliest_period
        if billing_profile:
            # Strip workspace_id from the user-level copy
            bp = {k: v for k, v in billing_profile.items() if k != "workspace_id"}
            update["billing_profile"] = bp
        await db.users.update_one({"id": u["id"]}, {"$set": update})
        moved += 1
        logger.info(
            "account_migration: user=%s email=%s plan=%s credits=%s",
            u["id"], u.get("email"), best_plan, credits_total,
        )
    return {
        "migrated_users": moved,
        "skipped_users": skipped,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


async def needs_migration() -> bool:
    """True when at least one user has no `plan` field yet."""
    db = get_db()
    missing = await db.users.count_documents({"plan": {"$exists": False}})
    return missing > 0
