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
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from db import get_db
from auth_utils import get_current_user, hash_password
from services.audit import log as audit_log
from services.plans import workspace_plan, list_plans

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
    workspace_id: str
    delta: int = Field(description="positive to grant, negative to revoke")
    reason: Optional[str] = None


@router.post("/admin/users/{user_id}/credits")
async def adjust_credits(user_id: str, payload: CreditsIn, request: Request):
    actor = await _require_admin(request)
    db = get_db()
    u = await db.users.find_one({"id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    ws = await db.workspaces.find_one({"id": payload.workspace_id})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.get("owner_id") != user_id:
        raise HTTPException(status_code=400, detail="Workspace is not owned by this user")
    current = int(ws.get("credits_balance") or 0)
    new_balance = max(0, current + payload.delta)
    await db.workspaces.update_one(
        {"id": payload.workspace_id},
        {"$set": {"credits_balance": new_balance}},
    )
    # Write a transaction row so the user can see the adjustment in their wallet history.
    await db.credit_transactions.insert_one({
        "id": __import__("uuid").uuid4().hex,
        "workspace_id": payload.workspace_id,
        "delta": payload.delta,
        "balance_after": new_balance,
        "kind": "admin_adjustment",
        "reason": payload.reason or "Manual admin adjustment",
        "actor_email": actor.get("email"),
        "created_at": _now_iso(),
    })
    audit_log(action="admin.user.credits_adjust", actor=actor,
              workspace_id=payload.workspace_id,
              resource_type="workspace", resource_id=payload.workspace_id,
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
    actor = await _require_admin(request)
    db = get_db()
    u = await db.users.find_one({"id": user_id})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    ws = await db.workspaces.find_one({"id": payload.workspace_id})
    if not ws or ws.get("owner_id") != user_id:
        raise HTTPException(status_code=400, detail="Workspace not owned by user")
    plan = next((p for p in await list_plans() if p["id"] == payload.plan), None)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan '{payload.plan}'")
    await db.workspaces.update_one(
        {"id": payload.workspace_id},
        {"$set": {"plan": payload.plan, "plan_changed_at": _now_iso()}},
    )
    audit_log(action="admin.user.plan_change", actor=actor,
              workspace_id=payload.workspace_id,
              resource_type="workspace", resource_id=payload.workspace_id,
              meta={"target_email": u.get("email"), "new_plan": payload.plan,
                    "previous_plan": ws.get("plan")},
              request=request)
    return {"plan": payload.plan}


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
