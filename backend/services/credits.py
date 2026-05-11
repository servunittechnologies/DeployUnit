"""Credit wallet — atomic deductions, monthly grants, audit log.

The wallet lives on the workspace document so it stays atomic with the
billing context. Every change goes through `consume_credits` /
`grant_credits` which also append to `credit_transactions` for an audit
trail.

Workspace credit fields (added on first use, sparse):
    credits_balance:        int (default 0)
    credits_period_start:   ISO-8601 string — when the current month started
    credits_granted_total:  int (lifetime stat, useful for analytics)

Transaction shape (credit_transactions collection):
    {
        "id":           uuid,
        "workspace_id": str,
        "type":         "grant" | "consume" | "topup" | "refund" | "admin",
        "amount":       int (positive int; sign is implied by type),
        "balance_after":int,
        "reason":       str (e.g. "monthly grant", "sms eu", "build overage"),
        "ref_id":       str | None (e.g. deployment id, message sid)
        "ref_type":     str | None ("deployment" | "sms" | "mollie_payment" | ...)
        "user_id":      str | None (who triggered, if applicable)
        "created_at":   ISO timestamp
    }
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException

from db import get_db
from services.plans import workspace_plan

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _log_transaction(
    *,
    workspace_id: str,
    type_: str,
    amount: int,
    balance_after: int,
    reason: str,
    ref_id: Optional[str] = None,
    ref_type: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    db = get_db()
    await db.credit_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "workspace_id": workspace_id,
        "type": type_,
        "amount": amount,
        "balance_after": balance_after,
        "reason": reason,
        "ref_id": ref_id,
        "ref_type": ref_type,
        "user_id": user_id,
        "created_at": _now_iso(),
    })


async def get_balance(workspace_id: str) -> dict:
    """Returns balance + period info + plan grant amount for the UI."""
    db = get_db()
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")
    plan = await workspace_plan(workspace_id)
    monthly_grant = int(plan.get("credits") or 0)
    period_start = ws.get("credits_period_start")
    # Compute next reset date (period_start + 30 days)
    next_reset = None
    if period_start:
        try:
            ps = datetime.fromisoformat(period_start.replace("Z", "+00:00"))
            next_reset = (ps + timedelta(days=30)).isoformat()
        except Exception:
            pass
    return {
        "balance": int(ws.get("credits_balance") or 0),
        "monthly_grant": monthly_grant,
        "period_start": period_start,
        "next_reset_at": next_reset,
        "granted_total": int(ws.get("credits_granted_total") or 0),
    }


async def consume_credits(
    workspace_id: str,
    amount: int,
    *,
    reason: str,
    ref_id: Optional[str] = None,
    ref_type: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """Atomically deduct `amount` from balance. Raises HTTPException(402) if
    insufficient. Returns the new balance dict.

    `amount` must be positive. Use small numbers — 1 cr ≈ €0.10.
    """
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")
    db = get_db()
    # Atomic conditional decrement
    res = await db.workspaces.find_one_and_update(
        {"id": workspace_id, "credits_balance": {"$gte": amount}},
        {"$inc": {"credits_balance": -amount}},
        projection={"_id": 0, "credits_balance": 1},
        return_document=True,  # post-update doc (PyMongo: motor uses bool flag)
    )
    if not res:
        # Either workspace missing, or insufficient credits.
        ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0, "credits_balance": 1})
        if not ws:
            raise HTTPException(status_code=404, detail="workspace not found")
        current = int(ws.get("credits_balance") or 0)
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits ({current} available, {amount} needed for {reason}). Buy a credit pack on the billing page.",
        )
    new_balance = int(res.get("credits_balance") or 0)
    await _log_transaction(
        workspace_id=workspace_id,
        type_="consume",
        amount=amount,
        balance_after=new_balance,
        reason=reason,
        ref_id=ref_id,
        ref_type=ref_type,
        user_id=user_id,
    )
    return {"balance": new_balance, "consumed": amount}


async def grant_credits(
    workspace_id: str,
    amount: int,
    *,
    reason: str,
    type_: str = "topup",
    ref_id: Optional[str] = None,
    ref_type: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """Add `amount` to balance. `type_` is one of: grant, topup, refund, admin."""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")
    db = get_db()
    res = await db.workspaces.find_one_and_update(
        {"id": workspace_id},
        {
            "$inc": {
                "credits_balance": amount,
                "credits_granted_total": amount,
            },
        },
        projection={"_id": 0, "credits_balance": 1},
        return_document=True,
    )
    if not res:
        raise HTTPException(status_code=404, detail="workspace not found")
    new_balance = int(res.get("credits_balance") or 0)
    await _log_transaction(
        workspace_id=workspace_id,
        type_=type_,
        amount=amount,
        balance_after=new_balance,
        reason=reason,
        ref_id=ref_id,
        ref_type=ref_type,
        user_id=user_id,
    )
    return {"balance": new_balance, "granted": amount}


async def monthly_grant_tick() -> int:
    """Scheduler job — runs daily. For each workspace whose plan grants
    credits, if their period_start is >= 30 days ago (or unset), reset the
    balance to plan.credits and start a new period. Returns # of workspaces
    that received credits this run.

    We use a 30-day rolling window keyed off `credits_period_start` rather
    than calendar months so signup-date determines anniversary. Cleaner UX
    and matches Mollie's subscription billing-cycle semantics.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=30)).isoformat()
    granted = 0
    cursor = db.workspaces.find(
        {
            "$or": [
                {"credits_period_start": {"$lte": cutoff}},
                {"credits_period_start": None},
                {"credits_period_start": {"$exists": False}},
            ],
        },
        {"_id": 0, "id": 1, "plan": 1, "credits_balance": 1, "credits_period_start": 1},
    )
    async for ws in cursor:
        plan = await workspace_plan(ws["id"])
        plan_credits = int(plan.get("credits") or 0)
        if plan_credits <= 0:
            # Still record period_start so we don't loop on free workspaces
            await db.workspaces.update_one(
                {"id": ws["id"]},
                {"$set": {"credits_period_start": now.isoformat()}},
            )
            continue
        # Reset (not increment) to the plan's grant. Unused credits expire —
        # this aligns with the simpler customer mental model + protects margins.
        # Top-ups bought separately go into a different bucket... but for v1
        # we keep one wallet; the reset would wipe top-ups too.
        # Compromise: only reset to MAX(current_balance, plan_credits). That
        # way users who topped up don't lose their purchase.
        current = int(ws.get("credits_balance") or 0)
        new_balance = max(current, plan_credits)
        delta = new_balance - current
        await db.workspaces.update_one(
            {"id": ws["id"]},
            {
                "$set": {
                    "credits_balance": new_balance,
                    "credits_period_start": now.isoformat(),
                },
                "$inc": {"credits_granted_total": max(0, delta)},
            },
        )
        if delta > 0:
            await _log_transaction(
                workspace_id=ws["id"],
                type_="grant",
                amount=delta,
                balance_after=new_balance,
                reason=f"monthly grant for {plan.get('name', plan.get('id'))} plan",
                ref_type="plan_grant",
            )
        granted += 1
    if granted:
        logger.info("credits monthly_grant_tick: %s workspaces refreshed", granted)
    return granted


async def list_transactions(workspace_id: str, limit: int = 50) -> list[dict]:
    db = get_db()
    return await db.credit_transactions.find(
        {"workspace_id": workspace_id},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)


# Credit pack catalog — one-shot Mollie payments
CREDIT_PACKS = {
    "small":  {"id": "small",  "credits": 50,  "price_eur": 5.0,  "label": "Small"},
    "medium": {"id": "medium", "credits": 220, "price_eur": 20.0, "label": "Medium ⭐", "bonus_pct": 10},
    "large":  {"id": "large",  "credits": 600, "price_eur": 50.0, "label": "Large", "bonus_pct": 17},
}


def get_pack(pack_id: str) -> Optional[dict]:
    return CREDIT_PACKS.get(pack_id)
