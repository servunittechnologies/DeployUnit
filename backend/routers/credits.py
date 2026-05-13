"""Credit-wallet REST endpoints.

  GET  /credits/balance?workspace_id=X        — balance + monthly grant + next reset
  GET  /credits/history?workspace_id=X        — last 50 transactions
  GET  /credits/packs                         — credit pack catalog
  POST /credits/checkout                      — start Mollie payment for a pack
  POST /admin/credits/grant                   — admin freebie / refund (admin-only)
"""
import logging
import os

from env_utils import public_base_url, mollie_webhook_url
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from clients.mollie import mollie, MollieError
from services.vat import compute_vat, compute_totals, effective_home_country
from services.credits import (
    get_balance, list_transactions, grant_credits, get_credit_packs, get_pack,
)

router = APIRouter(tags=["credits"])
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/credits/balance")
async def credits_balance(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    return await get_balance(workspace_id)


@router.get("/credits/history")
async def credits_history(workspace_id: str, request: Request, limit: int = 50):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    return await list_transactions(workspace_id, limit=min(200, max(1, limit)))


@router.get("/credits/packs")
async def credits_packs():
    return await get_credit_packs()


class CreditCheckoutIn(BaseModel):
    workspace_id: str
    pack: Optional[str] = None         # preset: "small" | "medium" | "large"
    custom_credits: Optional[int] = None  # OR custom amount (min 10)


# Custom top-up pricing: flat €0.10/credit, same rate as the smallest pack.
CUSTOM_RATE_EUR = 0.10
CUSTOM_MIN_CREDITS = 10
CUSTOM_MAX_CREDITS = 10000


@router.post("/credits/checkout")
async def credits_checkout(payload: CreditCheckoutIn, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(payload.workspace_id, user, ["owner", "admin", "billing"])

    # Resolve either a preset pack or a custom amount into a single
    # `pack`-shaped dict so the rest of the flow is identical.
    if payload.pack:
        pack = await get_pack(payload.pack)
        if not pack:
            raise HTTPException(status_code=400, detail="unknown pack")
    elif payload.custom_credits is not None:
        n = int(payload.custom_credits)
        if n < CUSTOM_MIN_CREDITS or n > CUSTOM_MAX_CREDITS:
            raise HTTPException(
                status_code=400,
                detail=f"custom amount must be between {CUSTOM_MIN_CREDITS} and {CUSTOM_MAX_CREDITS} credits",
            )
        pack = {
            "id": "custom",
            "label": f"Custom · {n} credits",
            "credits": n,
            "price_eur": round(n * CUSTOM_RATE_EUR, 2),
        }
    else:
        raise HTTPException(status_code=400, detail="pack or custom_credits required")
    if not mollie.configured:
        raise HTTPException(status_code=503, detail="payments are not configured")

    db = get_db()
    profile = await db.billing_profiles.find_one({"workspace_id": payload.workspace_id}, {"_id": 0}) or {}
    if not profile.get("country"):
        raise HTTPException(status_code=400, detail="add a billing profile first")

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
            "redirectUrl": f"{redirect}/app/billing?credit_pack={pack['id']}",
            "webhookUrl": webhook,
            "metadata": {
                "kind": "credit_pack",
                "workspace_id": payload.workspace_id,
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
        "workspace_id": payload.workspace_id,
        "pack_id": pack["id"],
        "credits": pack["credits"],
        "subtotal": totals["subtotal"],
        "vat_amount": totals["vat_amount"],
        "total": totals["total"],
        "mollie_payment_id": payment.get("id"),
        "status": "pending",
        "created_at": _now_iso(),
        "user_id": user["id"],
    })

    return {
        "checkout_url": payment.get("_links", {}).get("checkout", {}).get("href"),
        "pack": pack,
        "totals": totals,
    }


class AdminGrantIn(BaseModel):
    workspace_id: str
    amount: int
    reason: str = "admin grant"


@router.post("/admin/credits/grant")
async def admin_credits_grant(payload: AdminGrantIn, request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    return await grant_credits(
        payload.workspace_id,
        payload.amount,
        reason=payload.reason,
        type_="admin",
        user_id=user["id"],
    )
