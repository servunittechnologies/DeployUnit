"""Account-level routes (single source of truth for plan, credits, billing,
notification preferences). Replaces the previous workspace-scoped billing
flow: one plan + one wallet + one phone number per user, applied across
every workspace they own.

Endpoints (all require login):
  GET    /account                       — combined snapshot (profile + plan + usage + credits + notif)
  PATCH  /account/profile               — update display name
  POST   /account/password              — change password
  GET    /account/plan                  — plan details + account-wide usage
  POST   /account/plan/checkout         — start Mollie checkout for a plan upgrade
  POST   /account/plan/cancel           — cancel paid subscription (returns to Free)
  GET    /account/credits               — balance + monthly grant + next reset
  GET    /account/credits/history       — last N transactions
  POST   /account/credits/checkout      — buy a credit pack (Mollie)
  GET    /account/billing               — billing profile, subscription, payments, invoices
  PUT    /account/billing/profile       — upsert billing profile
"""
import logging
import os

from env_utils import public_base_url, mollie_webhook_url
import uuid
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from db import get_db
from auth_utils import get_current_user, verify_password, hash_password
from services.plans import user_plan, account_usage, list_plans, get_plan
from services.credits import (
    get_balance as credits_balance, list_transactions as credits_history,
    grant_credits, get_credit_packs, get_pack,
)
from services.audit import log as audit_log
from services.vat import (
    compute_vat, compute_totals, validate_vies, effective_home_country,
)
from clients.mollie import mollie, MollieError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["account"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_user(u: dict) -> dict:
    return {k: v for k, v in u.items() if k not in ("password_hash", "_id", "reset_token", "reset_token_expires_at")}


# ─────────────────────────── Snapshot ───────────────────────────
@router.get("/account")
async def account_snapshot(request: Request):
    """One call returns everything the account page needs: profile, plan,
    aggregated usage, credit wallet, notification prefs summary."""
    user = await get_current_user(request)
    db = get_db()
    plan = await user_plan(user["id"])
    usage = await account_usage(user["id"])
    credits = await credits_balance(user["id"])
    workspaces = await db.workspaces.find(
        {"owner_id": user["id"]}, {"_id": 0, "id": 1, "name": 1, "type": 1}
    ).to_list(50)
    sub = await db.subscriptions.find_one({"user_id": user["id"]}, {"_id": 0})
    if not sub:
        # Legacy fallback — look up by any workspace the user owns.
        ws_ids = [w["id"] for w in workspaces]
        if ws_ids:
            sub = await db.subscriptions.find_one(
                {"workspace_id": {"$in": ws_ids}}, {"_id": 0},
                sort=[("started_at", -1)],
            )
    return {
        "profile": _safe_user(user),
        "plan": plan,
        "usage": usage,
        "credits": credits,
        "subscription": sub,
        "workspaces": workspaces,
        "notif_prefs_summary": {
            "phone_set": bool((user.get("notification_prefs") or {}).get("phone_e164")),
            "slack_set": bool((user.get("notification_prefs") or {}).get("slack_webhook_url")),
            "discord_set": bool((user.get("notification_prefs") or {}).get("discord_webhook_url")),
        },
    }


# ─────────────────────────── Profile ───────────────────────────
class ProfileUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)


@router.patch("/account/profile")
async def update_profile(payload: ProfileUpdateIn, request: Request):
    user = await get_current_user(request)
    db = get_db()
    update = {}
    if payload.name:
        update["name"] = payload.name.strip()
    if not update:
        return _safe_user(user)
    await db.users.update_one({"id": user["id"]}, {"$set": update})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    audit_log(action="account.profile_update", actor=user,
              resource_type="user", resource_id=user["id"],
              meta=update, request=request)
    return _safe_user(fresh or user)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


@router.post("/account/password")
async def change_password(payload: PasswordChangeIn, request: Request):
    user = await get_current_user(request)
    db = get_db()
    fresh = await db.users.find_one({"id": user["id"]})
    if not fresh or not verify_password(payload.current_password, fresh.get("password_hash") or ""):
        raise HTTPException(status_code=400, detail="Current password is wrong")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_password(payload.new_password),
                  "password_updated_at": _now_iso()}},
    )
    audit_log(action="account.password_change", actor=user,
              resource_type="user", resource_id=user["id"],
              meta={}, request=request)
    return {"ok": True}


# ─────────────────────────── Plan + checkout ───────────────────────────
@router.get("/account/plan")
async def get_account_plan(request: Request):
    user = await get_current_user(request)
    plan = await user_plan(user["id"])
    usage = await account_usage(user["id"])
    plans = await list_plans(only_active=True)
    return {"plan": plan, "usage": usage, "available_plans": plans}


class PlanCheckoutIn(BaseModel):
    plan: Literal["free", "hobby", "pro", "agency"]


@router.post("/account/plan/checkout")
async def plan_checkout(payload: PlanCheckoutIn, request: Request):
    """Account-level plan switch. Downgrade to Free = immediate. Paid plan =
    returns a Mollie checkout URL."""
    user = await get_current_user(request)
    db = get_db()
    plan = await get_plan(payload.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")

    # Free / hobby — immediate switch (preserve the actual id chosen)
    if plan["id"] in ("free", "hobby"):
        # Find the user's CURRENT plan so we can refund unused fraction
        # of the OLD monthly fee back to credits.
        from services.resources import refund_plan_downgrade
        prev_user = await db.users.find_one({"id": user["id"]}, {"_id": 0, "plan": 1})
        prev_plan_id = (prev_user or {}).get("plan") or "free"
        sub = await db.subscriptions.find_one({"user_id": user["id"]})
        if sub and sub.get("mollie_subscription_id") and sub.get("status") not in ("canceled",):
            try:
                await mollie.cancel_subscription(
                    sub["mollie_customer_id"], sub["mollie_subscription_id"]
                )
            except Exception as e:
                logger.warning("cancel on downgrade failed: %s", e)
        await db.subscriptions.update_one(
            {"user_id": user["id"]},
            {"$set": {
                "id": (sub or {}).get("id") or str(uuid.uuid4()),
                "user_id": user["id"],
                "plan": plan["id"],
                "status": "active",
                "mollie_subscription_id": None,
                "mollie_customer_id": (sub or {}).get("mollie_customer_id"),
                "started_at": _now_iso(),
            }},
            upsert=True,
        )
        await db.users.update_one({"id": user["id"]}, {"$set": {"plan": plan["id"]}})
        refund_credits = 0
        if prev_plan_id != plan["id"]:
            try:
                refund_credits = await refund_plan_downgrade(
                    user["id"], from_plan_id=prev_plan_id, to_plan_id=plan["id"]
                )
            except Exception as e:
                logger.warning("plan downgrade refund failed: %s", e)
        audit_log(action="account.plan_downgrade", actor=user,
                  resource_type="user", resource_id=user["id"],
                  meta={"new_plan": plan["id"], "from_plan": prev_plan_id,
                        "refund_credits": refund_credits}, request=request)
        return {"plan": plan["id"], "status": "active",
                "checkout_url": None, "refund_credits": refund_credits}

    if not mollie.configured:
        raise HTTPException(status_code=503, detail="Payments not configured")

    profile = (await db.users.find_one({"id": user["id"]}, {"_id": 0, "billing_profile": 1}) or {}).get("billing_profile") or {}
    if not profile.get("country"):
        raise HTTPException(status_code=400, detail="Fill in your billing profile first.")

    vat = compute_vat(
        country=profile.get("country", ""),
        is_business=bool(profile.get("is_business")),
        has_valid_vat_id=bool(profile.get("vat_id_valid")),
        home_cc=await effective_home_country(),
    )
    totals = compute_totals(subtotal=float(plan["price"]), vat_rate=vat["rate"])

    # Ensure Mollie customer
    mc = await db.mollie_customers.find_one({"user_id": user["id"]})
    if not mc:
        try:
            cust = await mollie.create_customer(
                name=profile.get("company_name") or user.get("name") or user.get("email"),
                email=profile.get("email") or user.get("email"),
                metadata={"user_id": user["id"]},
            )
        except MollieError as e:
            raise HTTPException(status_code=502, detail=f"Mollie: {e}")
        cid = cust["id"]
        await db.mollie_customers.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "mollie_customer_id": cid,
            "created_at": _now_iso(),
        })
    else:
        cid = mc["mollie_customer_id"]

    redirect = public_base_url()
    webhook = mollie_webhook_url()
    try:
        payment = await mollie.create_payment(payload={
            "amount": {"currency": "EUR", "value": f"{totals['total']:.2f}"},
            "customerId": cid,
            "sequenceType": "first",
            "description": f"{plan['name']} plan — first payment",
            "redirectUrl": f"{redirect}/app/account?mollie=success",
            "webhookUrl": webhook,
            "metadata": {
                "user_id": user["id"],
                "plan": plan["id"],
                "kind": "first",
                "subtotal": f"{totals['subtotal']:.2f}",
                "vat_rate": str(vat["rate"]),
                "vat_amount": f"{totals['vat_amount']:.2f}",
                "vat_kind": vat["kind"],
            },
        })
    except MollieError as e:
        raise HTTPException(status_code=502, detail=f"Mollie: {e}")

    await db.payments.update_one(
        {"mollie_payment_id": payment["id"]},
        {"$set": {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "mollie_payment_id": payment["id"],
            "mollie_customer_id": cid,
            "kind": "first",
            "plan": plan["id"],
            "status": payment["status"],
            "currency": "EUR",
            "subtotal": totals["subtotal"],
            "vat_rate": vat["rate"],
            "vat_amount": totals["vat_amount"],
            "vat_note": vat["note"],
            "total": totals["total"],
            "created_at": _now_iso(),
        }},
        upsert=True,
    )
    await db.subscriptions.update_one(
        {"user_id": user["id"]},
        {"$set": {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "plan": plan["id"],
            "status": "pending",
            "mollie_customer_id": cid,
            "mollie_subscription_id": None,
            "started_at": _now_iso(),
        }},
        upsert=True,
    )
    checkout_url = ((payment.get("_links") or {}).get("checkout") or {}).get("href")
    audit_log(action="account.plan_checkout_start", actor=user,
              resource_type="user", resource_id=user["id"],
              meta={"target_plan": plan["id"], "total": totals["total"]},
              request=request)
    return {"plan": plan["id"], "status": "pending", "checkout_url": checkout_url}


@router.post("/account/plan/cancel")
async def plan_cancel(request: Request):
    user = await get_current_user(request)
    db = get_db()
    sub = await db.subscriptions.find_one({"user_id": user["id"]})
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")
    if sub.get("mollie_subscription_id") and sub.get("mollie_customer_id"):
        try:
            await mollie.cancel_subscription(sub["mollie_customer_id"], sub["mollie_subscription_id"])
        except MollieError as e:
            logger.warning("Mollie cancel error: %s", e)
    await db.subscriptions.update_one(
        {"user_id": user["id"]},
        {"$set": {"status": "canceled", "canceled_at": _now_iso()}},
    )
    await db.users.update_one({"id": user["id"]}, {"$set": {"plan": "free"}})
    audit_log(action="account.plan_cancel", actor=user,
              resource_type="user", resource_id=user["id"],
              meta={}, request=request)
    return {"status": "canceled"}


# ─────────────────────────── Credits ───────────────────────────
@router.get("/account/credits")
async def get_credits(request: Request):
    user = await get_current_user(request)
    return await credits_balance(user["id"])


@router.get("/account/credits/history")
async def get_credits_history(request: Request, limit: int = 50):
    user = await get_current_user(request)
    return await credits_history(user["id"], limit=min(200, max(1, limit)))


@router.get("/account/credits/packs")
async def get_credits_packs():
    return await get_credit_packs()


class CreditPackCheckoutIn(BaseModel):
    pack: str


@router.post("/account/credits/checkout")
async def credit_pack_checkout(payload: CreditPackCheckoutIn, request: Request):
    user = await get_current_user(request)
    pack = await get_pack(payload.pack)
    if not pack:
        raise HTTPException(status_code=400, detail="Unknown pack")
    if not mollie.configured:
        raise HTTPException(status_code=503, detail="Payments not configured")
    db = get_db()
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "billing_profile": 1})
    profile = (u or {}).get("billing_profile") or {}
    if not profile.get("country"):
        raise HTTPException(status_code=400, detail="Fill in your billing profile first.")
    vat = compute_vat(
        country=profile.get("country", ""),
        is_business=bool(profile.get("is_business")),
        has_valid_vat_id=bool(profile.get("vat_id_valid")),
        home_cc=await effective_home_country(),
    )
    totals = compute_totals(subtotal=pack["price_eur"], vat_rate=vat["rate"])
    redirect = public_base_url()
    webhook = mollie_webhook_url()
    try:
        payment = await mollie.create_payment(payload={
            "amount": {"currency": "EUR", "value": f"{totals['total']:.2f}"},
            "description": f"DeployUnit {pack['label']} pack — {pack['credits']} credits",
            "redirectUrl": f"{redirect}/app/account?credit_pack={pack['id']}",
            "webhookUrl": webhook,
            "metadata": {
                "kind": "credit_pack",
                "user_id": user["id"],
                "pack": pack["id"],
                "credits": pack["credits"],
                "vat_rate": vat["rate"],
                "vat_amount": totals["vat_amount"],
                "subtotal": totals["subtotal"],
            },
        })
    except MollieError as e:
        raise HTTPException(status_code=502, detail=f"mollie: {e}")
    await db.credit_pack_orders.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "pack_id": pack["id"],
        "credits": pack["credits"],
        "subtotal": totals["subtotal"],
        "vat_amount": totals["vat_amount"],
        "total": totals["total"],
        "mollie_payment_id": payment.get("id"),
        "status": "pending",
        "created_at": _now_iso(),
    })
    return {
        "checkout_url": payment.get("_links", {}).get("checkout", {}).get("href"),
        "pack": pack,
        "totals": totals,
    }


# ─────────────────────────── Billing ───────────────────────────
class BillingProfileIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=200)
    postal_code: str = Field(min_length=1, max_length=20)
    city: str = Field(min_length=1, max_length=80)
    country: str = Field(min_length=2, max_length=2)
    email: str = Field(min_length=3, max_length=120)
    vat_id: Optional[str] = None
    is_business: bool = False


@router.get("/account/billing")
async def get_account_billing(request: Request):
    user = await get_current_user(request)
    db = get_db()
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "billing_profile": 1})
    profile = (u or {}).get("billing_profile")
    sub = await db.subscriptions.find_one({"user_id": user["id"]}, {"_id": 0})
    if not sub:
        # Legacy fallback — owners had per-workspace subscriptions pre-migration.
        ws_ids = await db.workspaces.distinct("id", {"owner_id": user["id"]})
        if ws_ids:
            sub = await db.subscriptions.find_one(
                {"workspace_id": {"$in": ws_ids}}, {"_id": 0},
                sort=[("started_at", -1)],
            )
    # Combine user-keyed + legacy workspace-keyed payments/invoices for full history.
    ws_ids = await db.workspaces.distinct("id", {"owner_id": user["id"]})
    pay_q = {"$or": [{"user_id": user["id"]}]}
    inv_q = {"$or": [{"user_id": user["id"]}]}
    if ws_ids:
        pay_q["$or"].append({"workspace_id": {"$in": ws_ids}, "user_id": {"$exists": False}})
        inv_q["$or"].append({"workspace_id": {"$in": ws_ids}, "user_id": {"$exists": False}})
    payments = await db.payments.find(
        {"$and": [pay_q, {"plan": {"$exists": True, "$nin": ["free", "hobby"]}},
                  {"$or": [{"subtotal": {"$gt": 0}}, {"total": {"$gt": 0}}]}]},
        {"_id": 0},
    ).sort("created_at", -1).limit(24).to_list(24)
    invoices = await db.invoices.find(inv_q, {"_id": 0, "file_path": 0}).sort("invoice_date", -1).limit(24).to_list(24)
    for inv in invoices:
        inv["pdf_url"] = f"/api/billing/invoices/{inv['invoice_number']}/pdf"
    return {
        "billing_profile": profile,
        "subscription": sub,
        "payments": payments,
        "invoices": invoices,
        "mollie_available": mollie.configured,
    }


@router.put("/account/billing/profile")
async def upsert_billing_profile(payload: BillingProfileIn, request: Request):
    user = await get_current_user(request)
    db = get_db()
    vat_id_valid = None
    vat_holder = None
    if payload.is_business and payload.vat_id:
        res = await validate_vies(payload.vat_id)
        vat_id_valid = bool(res.get("valid"))
        vat_holder = res.get("name")
    vat = compute_vat(
        country=payload.country,
        is_business=payload.is_business,
        has_valid_vat_id=bool(vat_id_valid),
        home_cc=await effective_home_country(),
    )
    doc = {
        **payload.model_dump(),
        "vat_id_valid": vat_id_valid,
        "vat_id_holder_name": vat_holder,
        "vat_rate": vat["rate"],
        "vat_note": vat["note"],
        "vat_kind": vat["kind"],
        "updated_at": _now_iso(),
    }
    await db.users.update_one({"id": user["id"]}, {"$set": {"billing_profile": doc}})
    audit_log(action="account.billing_profile_update", actor=user,
              resource_type="user", resource_id=user["id"],
              meta={"country": payload.country, "is_business": payload.is_business},
              request=request)
    return {
        "profile": doc,
        "vat_id_valid": vat_id_valid,
        "vat_rate_applied": vat["rate"],
        "vat_note": vat["note"],
    }
