"""Credit wallet — atomic deductions, monthly grants, audit log.

The wallet lives on the USER document (account-level) — one wallet per
account, shared across all workspaces the user owns. This is a 2026-05-11
migration from workspace-scoped wallets; old call sites that still pass a
workspace_id are transparently resolved to the workspace's owner_id.

User credit fields (added on first use, sparse):
    credits_balance:        int (default 0)
    credits_period_start:   ISO-8601 string — when the current month started
    credits_granted_total:  int (lifetime stat, useful for analytics)

Transaction shape (credit_transactions collection):
    {
        "id":           uuid,
        "user_id":      str,       # NEW — account that owns the wallet
        "workspace_id": str|None,  # which workspace triggered the use (for context)
        "type":         "grant" | "consume" | "topup" | "refund" | "admin",
        "amount":       int (positive int; sign is implied by type),
        "balance_after":int,
        "reason":       str,
        "ref_id":       str | None,
        "ref_type":     str | None,
        "actor_user_id":str | None,
        "created_at":   ISO timestamp
    }
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException

from db import get_db
from services.plans import user_plan

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _resolve_user_id(workspace_or_user_id: str, *, kind_hint: Optional[str] = None) -> str:
    """Old call sites pass `workspace_id`; new sites pass `user_id`. We accept
    either. If the value matches a workspace row, we use the workspace owner;
    otherwise we assume it's already a user_id."""
    db = get_db()
    if kind_hint == "user":
        return workspace_or_user_id
    if kind_hint == "workspace":
        ws = await db.workspaces.find_one({"id": workspace_or_user_id}, {"_id": 0, "owner_id": 1})
        if not ws or not ws.get("owner_id"):
            raise HTTPException(status_code=404, detail="workspace has no owner")
        return ws["owner_id"]
    # Auto-detect — try workspace first, fall back to user.
    ws = await db.workspaces.find_one({"id": workspace_or_user_id}, {"_id": 0, "owner_id": 1})
    if ws and ws.get("owner_id"):
        return ws["owner_id"]
    return workspace_or_user_id


async def _log_transaction(
    *,
    user_id: str,
    workspace_id: Optional[str],
    type_: str,
    amount: int,
    balance_after: int,
    reason: str,
    ref_id: Optional[str] = None,
    ref_type: Optional[str] = None,
    actor_user_id: Optional[str] = None,
) -> None:
    db = get_db()
    await db.credit_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "workspace_id": workspace_id,
        "type": type_,
        "amount": amount,
        "balance_after": balance_after,
        "reason": reason,
        "ref_id": ref_id,
        "ref_type": ref_type,
        "actor_user_id": actor_user_id,
        "user_id_actor": actor_user_id,  # legacy alias for older readers
        "created_at": _now_iso(),
    })


async def get_balance(workspace_or_user_id: str) -> dict:
    """Returns balance + period info + plan grant amount for the UI. Accepts
    either a workspace_id (legacy) or user_id; resolves to the account."""
    db = get_db()
    user_id = await _resolve_user_id(workspace_or_user_id)
    u = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    plan = await user_plan(user_id)
    monthly_grant = int(plan.get("credits") or 0)
    period_start = u.get("credits_period_start")
    next_reset = None
    if period_start:
        try:
            ps = datetime.fromisoformat(period_start.replace("Z", "+00:00"))
            next_reset = (ps + timedelta(days=30)).isoformat()
        except Exception:
            pass
    return {
        "balance": int(u.get("credits_balance") or 0),
        "monthly_grant": monthly_grant,
        "period_start": period_start,
        "next_reset_at": next_reset,
        "granted_total": int(u.get("credits_granted_total") or 0),
    }


async def consume_credits(
    workspace_or_user_id: str,
    amount: int,
    *,
    reason: str,
    ref_id: Optional[str] = None,
    ref_type: Optional[str] = None,
    user_id: Optional[str] = None,  # actor (kept for compat — old kwarg name)
) -> dict:
    """Atomically deduct `amount` from the user's wallet. Accepts either a
    workspace_id (legacy) or a user_id."""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")
    db = get_db()
    target_user_id = await _resolve_user_id(workspace_or_user_id)
    # Used to know which workspace context to log (helps history)
    ws_context: Optional[str] = None
    if workspace_or_user_id != target_user_id:
        ws_context = workspace_or_user_id
    res = await db.users.find_one_and_update(
        {"id": target_user_id, "credits_balance": {"$gte": amount}},
        {"$inc": {"credits_balance": -amount}},
        projection={"_id": 0, "credits_balance": 1},
        return_document=True,
    )
    if not res:
        u = await db.users.find_one({"id": target_user_id}, {"_id": 0, "credits_balance": 1})
        if not u:
            raise HTTPException(status_code=404, detail="user not found")
        current = int(u.get("credits_balance") or 0)
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits ({current} available, {amount} needed for {reason}). Buy a credit pack on the account page.",
        )
    new_balance = int(res.get("credits_balance") or 0)
    await _log_transaction(
        user_id=target_user_id,
        workspace_id=ws_context,
        type_="consume",
        amount=amount,
        balance_after=new_balance,
        reason=reason,
        ref_id=ref_id,
        ref_type=ref_type,
        actor_user_id=user_id,
    )
    return {"balance": new_balance, "consumed": amount}


async def grant_credits(
    workspace_or_user_id: str,
    amount: int,
    *,
    reason: str,
    type_: str = "topup",
    ref_id: Optional[str] = None,
    ref_type: Optional[str] = None,
    user_id: Optional[str] = None,  # actor
) -> dict:
    """Add `amount` to the user's wallet. `type_`: grant|topup|refund|admin."""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")
    db = get_db()
    target_user_id = await _resolve_user_id(workspace_or_user_id)
    ws_context: Optional[str] = None
    if workspace_or_user_id != target_user_id:
        ws_context = workspace_or_user_id
    res = await db.users.find_one_and_update(
        {"id": target_user_id},
        {"$inc": {"credits_balance": amount, "credits_granted_total": amount}},
        projection={"_id": 0, "credits_balance": 1},
        return_document=True,
    )
    if not res:
        raise HTTPException(status_code=404, detail="user not found")
    new_balance = int(res.get("credits_balance") or 0)
    await _log_transaction(
        user_id=target_user_id,
        workspace_id=ws_context,
        type_=type_,
        amount=amount,
        balance_after=new_balance,
        reason=reason,
        ref_id=ref_id,
        ref_type=ref_type,
        actor_user_id=user_id,
    )
    return {"balance": new_balance, "granted": amount}


async def monthly_grant_tick() -> int:
    """Scheduler job — runs daily. For each user whose plan grants credits,
    if their period_start is >= 30 days ago (or unset), top up to plan.credits
    and start a new period. Returns # of users that received credits."""
    db = get_db()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=30)).isoformat()
    granted = 0
    cursor = db.users.find(
        {
            "$or": [
                {"credits_period_start": {"$lte": cutoff}},
                {"credits_period_start": None},
                {"credits_period_start": {"$exists": False}},
            ],
        },
        {"_id": 0, "id": 1, "plan": 1, "credits_balance": 1, "credits_period_start": 1},
    )
    async for u in cursor:
        plan = await user_plan(u["id"])
        plan_credits = int(plan.get("credits") or 0)
        if plan_credits <= 0:
            await db.users.update_one(
                {"id": u["id"]},
                {"$set": {"credits_period_start": now.isoformat()}},
            )
            continue
        current = int(u.get("credits_balance") or 0)
        new_balance = max(current, plan_credits)
        delta = new_balance - current
        await db.users.update_one(
            {"id": u["id"]},
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
                user_id=u["id"],
                workspace_id=None,
                type_="grant",
                amount=delta,
                balance_after=new_balance,
                reason=f"monthly grant for {plan.get('name', plan.get('id'))} plan",
                ref_type="plan_grant",
            )
        granted += 1
    if granted:
        logger.info("credits monthly_grant_tick: %s users refreshed", granted)
    return granted


async def list_transactions(workspace_or_user_id: str, limit: int = 50) -> list[dict]:
    """List recent transactions. Accepts user_id or workspace_id (legacy).
    Returns rows for the resolved user — across all their workspaces."""
    db = get_db()
    user_id = await _resolve_user_id(workspace_or_user_id)
    # Match new rows (keyed by user_id) AND legacy rows (keyed by workspace_id
    # for workspaces this user owns) so history pre-migration still shows up.
    legacy_ws_ids = await db.workspaces.distinct("id", {"owner_id": user_id})
    q = {"$or": [{"user_id": user_id}]}
    if legacy_ws_ids:
        q["$or"].append({"user_id": {"$exists": False}, "workspace_id": {"$in": legacy_ws_ids}})
    return await db.credit_transactions.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)


# Credit pack catalog — one-shot Mollie payments
CREDIT_PACKS = {
    "small":  {"id": "small",  "credits": 50,  "price_eur": 5.0,  "label": "Small"},
    "medium": {"id": "medium", "credits": 220, "price_eur": 20.0, "label": "Medium ⭐", "bonus_pct": 10},
    "large":  {"id": "large",  "credits": 600, "price_eur": 50.0, "label": "Large", "bonus_pct": 17},
}


def get_pack(pack_id: str) -> Optional[dict]:
    return CREDIT_PACKS.get(pack_id)
