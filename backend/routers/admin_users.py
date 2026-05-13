"""Platform admin: per-user management.

Everything a support agent needs to operate a user:
  * GET    /admin/users                       — paged + searchable list
  * GET    /admin/users/{user_id}             — full profile (workspaces, plans,
                                                 credits, payments, audit)
  * POST   /admin/users/{user_id}/password    — set a new password (forces re-login)
  * POST   /admin/users/{user_id}/role        — admin <→ user
  * POST   /admin/users/{user_id}/suspend     — toggle is_active
  * DELETE /admin/users/{user_id}             — hard delete + cascade
  * POST   /admin/users/{user_id}/credits     — add/subtract credits on a workspace
  * POST   /admin/users/{user_id}/plan        — change a workspace's plan
  * GET    /admin/users/{user_id}/payments    — payments + invoices with txn IDs

All actions write an audit_log entry so a paper trail exists.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from db import get_db
from auth_utils import get_current_user, hash_password
from services.audit import log as audit_log
from services.plans import workspace_plan, list_plans, get_plan
from clients.mollie import mollie, MollieError
import os

router = APIRouter(tags=["admin-users"])
logger = logging.getLogger(__name__)


async def _require_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_user(u: dict) -> dict:
    """Strip secrets before handing to the admin UI."""
    out = {k: v for k, v in u.items() if k not in ("password_hash", "_id", "reset_token", "reset_token_expires_at")}
    return out


# ─────────────────────── List + detail ───────────────────────
@router.get("/admin/users")
async def list_users(
    request: Request,
    q: Optional[str] = Query(default=None, description="search email/name"),
    role: Optional[str] = Query(default=None),
    active: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    await _require_admin(request)
    db = get_db()
    filt: dict = {}
    if q:
        filt["$or"] = [
            {"email": {"$regex": q, "$options": "i"}},
            {"name": {"$regex": q, "$options": "i"}},
            {"github_login": {"$regex": q, "$options": "i"}},
        ]
    if role:
        filt["role"] = role
    if active is not None:
        filt["is_active"] = active
    total = await db.users.count_documents(filt)
    rows = await db.users.find(filt, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    # Enrich each row with a quick KPI snapshot (workspaces count, total credits)
    enriched = []
    for u in rows:
        ws_ids = await db.workspaces.distinct("id", {"owner_id": u["id"]})
        credits = 0
        if ws_ids:
            agg = await db.workspaces.aggregate([
                {"$match": {"id": {"$in": ws_ids}}},
                {"$group": {"_id": None, "c": {"$sum": "$credits_balance"}}},
            ]).to_list(1)
            credits = (agg[0].get("c") if agg else 0) or 0
        enriched.append({**_redact_user(u), "workspaces_count": len(ws_ids), "credits_total": int(credits)})
    return {"users": enriched, "total": total, "limit": limit, "offset": offset}


@router.get("/admin/users/{user_id}")
async def get_user(user_id: str, request: Request):
    await _require_admin(request)
    db = get_db()
    u = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    workspaces = await db.workspaces.find({"owner_id": user_id}, {"_id": 0}).to_list(50)
    enriched_ws = []
    for w in workspaces:
        plan = await workspace_plan(w["id"])
        ws_payments = await db.payments.count_documents({"workspace_id": w["id"]})
        apps = await db.apps.count_documents({"workspace_id": w["id"]})
        enriched_ws.append({
            **w,
            "plan_details": {"id": plan.get("id"), "name": plan.get("name"), "price": plan.get("price")},
            "apps_count": apps,
            "payments_count": ws_payments,
        })
    # User-scope audit log (actions where this user is the actor)
    audits = await db.audit_log.find({"actor_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(40).to_list(40)
    return {
        "user": _redact_user(u),
        "workspaces": enriched_ws,
        "audit": audits,
        "available_plans": await list_plans(),
    }


# ─────────────────────── Password reset ───────────────────────
class PasswordIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)


@router.post("/admin/users/{user_id}/password")
async def set_password(user_id: str, payload: PasswordIn, request: Request):
    actor = await _require_admin(request)
    db = get_db()
    u = await db.users.find_one({"id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash": hash_password(payload.new_password),
            "password_updated_at": _now_iso(),
        }},
    )
    # Fire-and-forget email so the user knows their password changed + what it is.
    try:
        from services.emails import send_password_reset_admin
        import asyncio as _asyncio
        _asyncio.create_task(send_password_reset_admin(u, payload.new_password, actor.get("email")))
    except Exception as e:
        logger.warning("admin password reset email failed: %s", e)
    audit_log(action="admin.user.password_reset", actor=actor,
              resource_type="user", resource_id=user_id,
              meta={"target_email": u.get("email")}, request=request)
    return {"ok": True}


# ─────────────────────── Role / suspend / delete ───────────────────────
class RoleIn(BaseModel):
    role: Literal["admin", "user"]


@router.post("/admin/users/{user_id}/role")
async def set_role(user_id: str, payload: RoleIn, request: Request):
    actor = await _require_admin(request)
    db = get_db()
    u = await db.users.find_one({"id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    # Prevent the last admin from demoting themselves into a dead-locked platform
    if payload.role == "user" and u.get("role") == "admin":
        admins = await db.users.count_documents({"role": "admin", "is_active": {"$ne": False}})
        if admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last admin")
    await db.users.update_one({"id": user_id}, {"$set": {"role": payload.role}})
    audit_log(action="admin.user.role_change", actor=actor,
              resource_type="user", resource_id=user_id,
              meta={"target_email": u.get("email"), "new_role": payload.role}, request=request)
    return {"role": payload.role}


@router.post("/admin/users/{user_id}/suspend")
async def toggle_suspend(user_id: str, request: Request):
    actor = await _require_admin(request)
    db = get_db()
    u = await db.users.find_one({"id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if u.get("id") == actor.get("id"):
        raise HTTPException(status_code=400, detail="You cannot suspend yourself")
    new_active = not u.get("is_active", True)
    await db.users.update_one({"id": user_id}, {"$set": {"is_active": new_active}})
    audit_log(action="admin.user.suspend" if not new_active else "admin.user.unsuspend",
              actor=actor, resource_type="user", resource_id=user_id,
              meta={"target_email": u.get("email")}, request=request)
    return {"is_active": new_active}


@router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, request: Request):
    """Hard-delete a user. Cascades workspace ownership/orphan apps to admin.
    Keep yourself safe — can't delete yourself or the last admin."""
    actor = await _require_admin(request)
    db = get_db()
    u = await db.users.find_one({"id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if u.get("id") == actor.get("id"):
        raise HTTPException(status_code=400, detail="You cannot delete yourself")
    if u.get("role") == "admin":
        admins = await db.users.count_documents({"role": "admin", "is_active": {"$ne": False}})
        if admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin")
    await db.users.delete_one({"id": user_id})
    # Detach memberships; leave workspaces around but flagged ownerless
    await db.workspace_members.delete_many({"user_id": user_id})
    await db.workspaces.update_many({"owner_id": user_id}, {"$set": {"owner_id": None}})
    audit_log(action="admin.user.delete", actor=actor,
              resource_type="user", resource_id=user_id,
              meta={"target_email": u.get("email")}, request=request)
    return {"deleted": True}


# ─────────────────────── Credits ───────────────────────
class CreditsIn(BaseModel):
    workspace_id: Optional[str] = None  # legacy; ignored if absent
    delta: int = Field(description="positive to grant, negative to revoke")
    reason: Optional[str] = None


@router.post("/admin/users/{user_id}/credits")
async def adjust_credits(user_id: str, payload: CreditsIn, request: Request):
    """Top up or deduct credits on a user's account-level wallet.
    `workspace_id` is kept on the payload for backward compat with the old
    admin UI but is logged only as context — the wallet itself is user-scoped now.
    """
    from services.credits import grant_credits, consume_credits
    actor = await _require_admin(request)
    db = get_db()
    u = await db.users.find_one({"id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    ws_id = payload.workspace_id
    if ws_id:
        ws = await db.workspaces.find_one({"id": ws_id})
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
    if payload.delta > 0:
        result = await grant_credits(
            user_id, payload.delta,
            reason=payload.reason or f"admin top-up by {actor.get('email')}",
            type_="admin",
            ref_id=ws_id, ref_type="admin_adjustment",
            user_id=actor["id"],
        )
        new_balance = result["balance"]
    elif payload.delta < 0:
        try:
            result = await consume_credits(
                user_id, abs(payload.delta),
                reason=payload.reason or f"admin deduction by {actor.get('email')}",
                ref_id=ws_id, ref_type="admin_adjustment",
                user_id=actor["id"],
            )
            new_balance = result["balance"]
        except HTTPException as e:
            if e.status_code == 402:
                # Allow forced deduction to 0 if insufficient
                u2 = await db.users.find_one({"id": user_id}, {"_id": 0, "credits_balance": 1})
                current = int((u2 or {}).get("credits_balance") or 0)
                if current > 0:
                    result = await consume_credits(
                        user_id, current,
                        reason=f"admin forced deduction (cap at 0) by {actor.get('email')}",
                        ref_id=ws_id, ref_type="admin_adjustment",
                        user_id=actor["id"],
                    )
                    new_balance = result["balance"]
                else:
                    new_balance = 0
            else:
                raise
    else:
        u2 = await db.users.find_one({"id": user_id}, {"_id": 0, "credits_balance": 1})
        new_balance = int((u2 or {}).get("credits_balance") or 0)
    audit_log(action="admin.user.credits_adjust", actor=actor,
              workspace_id=ws_id,
              resource_type="user", resource_id=user_id,
              meta={"target_email": u.get("email"), "delta": payload.delta,
                    "new_balance": new_balance, "reason": payload.reason},
              request=request)
    return {"balance": new_balance, "delta": payload.delta}


# ─────────────────────── Plan change ───────────────────────
class PlanIn(BaseModel):
    workspace_id: str
    plan: str


@router.post("/admin/users/{user_id}/plan")
async def set_plan(user_id: str, payload: PlanIn, request: Request):
    """Switch this user's account plan.

    The platform stores the plan on the OWNER USER (users.plan); every
    workspace the user owns inherits it. The legacy field workspaces.plan
    is kept in sync for backwards-compat with old reports, but is no
    longer the source of truth.

    If the user has an active Mollie subscription we PATCH it to the new
    price so the next recurring charge bills the correct amount. If the
    target is the free plan, we cancel the Mollie subscription instead.
    """
    actor = await _require_admin(request)
    db = get_db()
    u = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    ws = await db.workspaces.find_one({"id": payload.workspace_id}, {"_id": 0})
    if not ws or ws.get("owner_id") != user_id:
        raise HTTPException(status_code=400, detail="Workspace not owned by user")
    plan = await get_plan(payload.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan '{payload.plan}'")

    previous_plan = u.get("plan") or ws.get("plan") or "free"
    now = _now_iso()

    # Source of truth — user account plan.
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"plan": payload.plan, "plan_changed_at": now}},
    )
    # Keep every workspace this user owns in sync (legacy field used by
    # some reports/queries). One write, many docs.
    await db.workspaces.update_many(
        {"owner_id": user_id},
        {"$set": {"plan": payload.plan, "plan_changed_at": now}},
    )

    # Sync Mollie subscription if the user has one.
    mollie_synced = False
    mollie_action = "none"
    mollie_error: Optional[str] = None
    sub = await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0})
    cust_id = (sub or {}).get("mollie_customer_id")
    sub_id = (sub or {}).get("mollie_subscription_id")
    if sub and cust_id and sub_id and mollie.configured:
        try:
            if payload.plan in ("free", "hobby"):
                await mollie.cancel_subscription(cust_id, sub_id)
                await db.subscriptions.update_one(
                    {"user_id": user_id},
                    {"$set": {"status": "cancelled", "plan": "free",
                              "cancelled_at": now, "cancelled_by": "admin"}},
                )
                mollie_action = "cancelled"
                mollie_synced = True
            elif float(plan.get("price") or 0) > 0:
                await mollie.update_subscription(cust_id, sub_id, payload={
                    "amount": {"currency": "EUR", "value": f"{float(plan['price']):.2f}"},
                    "description": f"{plan['name']} plan subscription",
                    "metadata": {"user_id": user_id, "plan": plan["id"]},
                })
                await db.subscriptions.update_one(
                    {"user_id": user_id},
                    {"$set": {"plan": plan["id"], "status": "active",
                              "updated_at": now}},
                )
                mollie_action = "updated"
                mollie_synced = True
        except MollieError as e:
            logger.warning("admin plan change Mollie sync failed for user %s: %s", user_id, e)
            mollie_error = str(e)
        except Exception as e:
            logger.warning("admin plan change Mollie sync unexpected: %s", e)
            mollie_error = str(e)

    audit_log(action="admin.user.plan_change", actor=actor,
              workspace_id=payload.workspace_id,
              resource_type="workspace", resource_id=payload.workspace_id,
              meta={"target_email": u.get("email"), "new_plan": payload.plan,
                    "previous_plan": previous_plan,
                    "mollie_action": mollie_action,
                    "mollie_synced": mollie_synced,
                    "mollie_error": mollie_error},
              request=request)
    return {
        "plan": payload.plan,
        "previous_plan": previous_plan,
        "mollie_synced": mollie_synced,
        "mollie_action": mollie_action,
        "mollie_error": mollie_error,
    }


# ─────────────────────── Payments / invoices ───────────────────────
@router.get("/admin/users/{user_id}/payments")
async def user_payments(user_id: str, request: Request):
    """Payments + invoices grouped by workspace, with transaction IDs."""
    await _require_admin(request)
    db = get_db()
    u = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    ws_ids = await db.workspaces.distinct("id", {"owner_id": user_id})
    if not ws_ids:
        return {"workspaces": [], "totals": {"paid_eur": 0.0, "payments": 0, "invoices": 0}}

    by_ws = []
    total_paid = 0.0
    total_payments = 0
    total_invoices = 0
    for wid in ws_ids:
        ws = await db.workspaces.find_one({"id": wid}, {"_id": 0})
        payments = await db.payments.find({"workspace_id": wid}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
        invoices = await db.invoices.find({"workspace_id": wid}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
        paid_eur = sum(float(p.get("total") or 0) for p in payments if p.get("status") == "paid")
        total_paid += paid_eur
        total_payments += len(payments)
        total_invoices += len(invoices)
        by_ws.append({
            "workspace": {"id": ws["id"], "name": ws["name"], "plan": ws.get("plan")},
            "paid_eur": round(paid_eur, 2),
            "payments": payments,
            "invoices": invoices,
        })
    return {
        "workspaces": by_ws,
        "totals": {"paid_eur": round(total_paid, 2), "payments": total_payments, "invoices": total_invoices},
    }
