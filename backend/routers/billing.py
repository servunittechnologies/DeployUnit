"""Billing routes — Mollie Subscriptions + EU VAT + PDF invoices.

Flow:
1. PUT /billing/profile       — save company/VAT details; validate VAT ID with VIES
2. POST /billing/checkout     — ensure Mollie customer exists, create first payment, return checkout URL
3. (browser) User pays on Mollie, returns to /app/billing?mollie=success
4. POST /billing/mollie/webhook (Mollie) — fetches payment; if first paid, creates subscription; records payment + invoice
5. POST /billing/cancel       — cancel subscription at Mollie, mark canceled locally
6. GET  /billing/invoices     — list invoices; /billing/invoices/{n}/pdf streams the PDF
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from models import BillingProfileIn, CheckoutIn
from clients.mollie import mollie, MollieError
from services.vat import (
    compute_vat, compute_totals, validate_vies, EU_VAT_RATES, COUNTRY_NAMES, is_eu,
    effective_home_country,
)
from services.invoice import render_invoice_pdf, file_path_for, effective_company
from services.plans import list_plans as plans_list, get_plan as plans_get

logger = logging.getLogger(__name__)
router = APIRouter(tags=["billing"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/billing/plans")
async def list_plans():
    return await plans_list(only_active=True)


@router.get("/billing/countries")
async def list_countries():
    eu = [{"code": c, "name": COUNTRY_NAMES.get(c, c), "eu": True, "vat_rate": EU_VAT_RATES[c]} for c in EU_VAT_RATES]
    eu.sort(key=lambda x: x["name"])
    extras = [{"code": c, "name": COUNTRY_NAMES.get(c, c), "eu": False} for c in ["US", "GB", "CA", "CH", "NO", "AU"]]
    return eu + extras


# ---------- Billing profile ----------
@router.get("/billing/profile")
async def get_profile(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    profile = await db.billing_profiles.find_one({"workspace_id": workspace_id}, {"_id": 0})
    return profile


@router.put("/billing/profile")
async def upsert_profile(workspace_id: str, payload: BillingProfileIn, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user, ["owner", "admin", "billing"])
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
        "workspace_id": workspace_id,
        **payload.model_dump(),
        "vat_id_valid": vat_id_valid,
        "vat_id_holder_name": vat_holder,
        "vat_rate": vat["rate"],
        "vat_note": vat["note"],
        "vat_kind": vat["kind"],
        "updated_at": _now_iso(),
    }
    await db.billing_profiles.update_one(
        {"workspace_id": workspace_id}, {"$set": doc}, upsert=True
    )
    return {
        "profile": {**doc},
        "vat_id_valid": vat_id_valid,
        "vat_rate_applied": vat["rate"],
        "vat_note": vat["note"],
    }


# ---------- Subscription / checkout ----------
@router.get("/billing/subscription")
async def get_subscription(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    sub = await db.subscriptions.find_one({"workspace_id": workspace_id}, {"_id": 0})
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    profile = await db.billing_profiles.find_one({"workspace_id": workspace_id}, {"_id": 0})
    payments = await db.payments.find(
        {"workspace_id": workspace_id}, {"_id": 0}
    ).sort("created_at", -1).limit(12).to_list(12)
    return {
        "plan": (ws or {}).get("plan", "free"),
        "subscription": sub,
        "billing_profile": profile,
        "payments": payments,
        "mollie_available": mollie.configured,
    }


async def _ensure_mollie_customer(workspace: dict, profile: dict) -> str:
    db = get_db()
    existing = await db.mollie_customers.find_one({"workspace_id": workspace["id"]})
    if existing:
        return existing["mollie_customer_id"]
    customer = await mollie.create_customer(
        name=profile.get("company_name") or workspace["name"],
        email=profile["email"],
        metadata={"workspace_id": workspace["id"]},
    )
    cid = customer["id"]
    await db.mollie_customers.insert_one({
        "id": str(uuid.uuid4()),
        "workspace_id": workspace["id"],
        "mollie_customer_id": cid,
        "created_at": _now_iso(),
    })
    return cid


@router.post("/billing/checkout")
async def checkout(payload: CheckoutIn, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(payload.workspace_id, user, ["owner", "admin", "billing"])
    db = get_db()

    plan = await plans_get(payload.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")

    ws = await db.workspaces.find_one({"id": payload.workspace_id})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Free plan — activate without Mollie
    if plan["id"] in ("free", "hobby"):
        # Cancel any existing active subscription at Mollie
        existing_sub = await db.subscriptions.find_one({"workspace_id": payload.workspace_id})
        if existing_sub and existing_sub.get("mollie_subscription_id") and existing_sub.get("status") not in ("canceled",):
            try:
                await mollie.cancel_subscription(
                    existing_sub["mollie_customer_id"],
                    existing_sub["mollie_subscription_id"],
                )
            except Exception as e:
                logger.warning("cancel on downgrade failed: %s", e)
        await db.subscriptions.update_one(
            {"workspace_id": payload.workspace_id},
            {"$set": {
                "id": existing_sub["id"] if existing_sub else str(uuid.uuid4()),
                "workspace_id": payload.workspace_id,
                "plan": "free",
                "status": "active",
                "mollie_subscription_id": None,
                "mollie_customer_id": (existing_sub or {}).get("mollie_customer_id"),
                "started_at": _now_iso(),
            }},
            upsert=True,
        )
        await db.workspaces.update_one({"id": payload.workspace_id}, {"$set": {"plan": "free"}})
        return {"plan": "free", "status": "active", "checkout_url": None}

    if not mollie.configured:
        raise HTTPException(status_code=500, detail="Mollie not configured")

    profile = await db.billing_profiles.find_one({"workspace_id": payload.workspace_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=400, detail="Fill in your billing profile first (company, address, country).")

    # Compute VAT for the first payment
    vat = compute_vat(
        country=profile.get("country", ""),
        is_business=bool(profile.get("is_business")),
        has_valid_vat_id=bool(profile.get("vat_id_valid")),
        home_cc=await effective_home_country(),
    )
    totals = compute_totals(subtotal=float(plan["price"]), vat_rate=vat["rate"])

    try:
        mollie_customer_id = await _ensure_mollie_customer(ws, profile)
    except MollieError as e:
        raise HTTPException(status_code=502, detail=f"Mollie customer: {e}")

    # Create first payment (establishes mandate)
    payload_payment = {
        "amount": {"currency": "EUR", "value": f"{totals['total']:.2f}"},
        "customerId": mollie_customer_id,
        "sequenceType": "first",
        "description": f"{plan['name']} plan — first payment",
        "redirectUrl": os.environ.get("MOLLIE_REDIRECT_URL"),
        "webhookUrl": os.environ.get("MOLLIE_WEBHOOK_URL"),
        "metadata": {
            "workspace_id": payload.workspace_id,
            "plan": plan["id"],
            "kind": "first",
            "subtotal": f"{totals['subtotal']:.2f}",
            "vat_rate": str(vat["rate"]),
            "vat_amount": f"{totals['vat_amount']:.2f}",
            "vat_kind": vat["kind"],
        },
    }
    try:
        payment = await mollie.create_payment(payload=payload_payment)
    except MollieError as e:
        raise HTTPException(status_code=502, detail=f"Mollie payment: {e}")

    # Persist payment row as pending
    await db.payments.update_one(
        {"mollie_payment_id": payment["id"]},
        {"$set": {
            "id": str(uuid.uuid4()),
            "workspace_id": payload.workspace_id,
            "mollie_payment_id": payment["id"],
            "mollie_customer_id": mollie_customer_id,
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
    # Provisional subscription row
    await db.subscriptions.update_one(
        {"workspace_id": payload.workspace_id},
        {"$set": {
            "id": str(uuid.uuid4()),
            "workspace_id": payload.workspace_id,
            "plan": plan["id"],
            "status": "pending",
            "mollie_customer_id": mollie_customer_id,
            "mollie_subscription_id": None,
            "started_at": _now_iso(),
        }},
        upsert=True,
    )

    checkout_url = ((payment.get("_links") or {}).get("checkout") or {}).get("href")
    return {
        "plan": plan["id"],
        "status": "pending",
        "checkout_url": checkout_url,
        "payment_id": payment["id"],
        "mollie_available": True,
    }


@router.post("/billing/cancel")
async def cancel(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user, ["owner", "admin", "billing"])
    db = get_db()
    sub = await db.subscriptions.find_one({"workspace_id": workspace_id})
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")
    if sub.get("mollie_subscription_id") and sub.get("mollie_customer_id"):
        try:
            await mollie.cancel_subscription(sub["mollie_customer_id"], sub["mollie_subscription_id"])
        except MollieError as e:
            logger.warning("Mollie cancel error: %s", e)
    await db.subscriptions.update_one(
        {"workspace_id": workspace_id},
        {"$set": {"status": "canceled", "canceled_at": _now_iso()}},
    )
    await db.workspaces.update_one({"id": workspace_id}, {"$set": {"plan": "free"}})
    return {"status": "canceled"}


# ---------- Webhook + invoice pipeline ----------
async def _next_invoice_number(db) -> str:
    year = datetime.now(timezone.utc).year
    latest = await db.invoices.find_one(
        {"invoice_number": {"$regex": f"^{year}-"}},
        sort=[("invoice_number", -1)],
    )
    seq = 1
    if latest:
        try:
            seq = int(latest["invoice_number"].split("-")[1]) + 1
        except Exception:
            seq = 1
    return f"{year}-{seq:04d}"


async def _generate_invoice_for_payment(db, payment_row: dict):
    if not payment_row or payment_row.get("status") != "paid":
        return None
    # Idempotency — one invoice per mollie_payment_id
    existing = await db.invoices.find_one({"mollie_payment_id": payment_row["mollie_payment_id"]}, {"_id": 0})
    if existing:
        return existing

    workspace_id = payment_row["workspace_id"]
    profile = await db.billing_profiles.find_one({"workspace_id": workspace_id}, {"_id": 0}) or {}
    plan_id = payment_row.get("plan") or "pro"
    plan = (await plans_get(plan_id)) or {"name": plan_id, "price": payment_row.get("subtotal", 0.0)}

    invoice_number = await _next_invoice_number(db)
    now = datetime.now(timezone.utc)
    items = [{
        "description": f"{plan['name']} plan — {now.strftime('%B %Y')}",
        "quantity": 1,
        "unit_price": payment_row["subtotal"],
    }]
    buyer = {
        "company_name": profile.get("company_name"),
        "address": profile.get("address"),
        "postal_code": profile.get("postal_code"),
        "city": profile.get("city"),
        "country": profile.get("country"),
        "email": profile.get("email"),
        "vat_id": profile.get("vat_id"),
    }
    pdf_path = render_invoice_pdf(
        invoice_number=invoice_number,
        buyer=buyer,
        items=items,
        subtotal=payment_row["subtotal"],
        vat_rate=payment_row["vat_rate"],
        vat_amount=payment_row["vat_amount"],
        vat_note=payment_row.get("vat_note") or "",
        total=payment_row["total"],
        currency=payment_row.get("currency", "EUR"),
        invoice_date=now,
        due_date=now + timedelta(days=0),  # paid immediately via Mollie
        payment_method=payment_row.get("method"),
        mollie_payment_id=payment_row["mollie_payment_id"],
        status="paid",
        company=await effective_company(),
    )
    doc = {
        "id": str(uuid.uuid4()),
        "workspace_id": workspace_id,
        "invoice_number": invoice_number,
        "mollie_payment_id": payment_row["mollie_payment_id"],
        "subtotal": payment_row["subtotal"],
        "vat_rate": payment_row["vat_rate"],
        "vat_amount": payment_row["vat_amount"],
        "vat_note": payment_row.get("vat_note") or "",
        "total": payment_row["total"],
        "currency": payment_row.get("currency", "EUR"),
        "status": "paid",
        "invoice_date": now.isoformat(),
        "due_date": now.isoformat(),
        "file_path": pdf_path,
        "buyer": buyer,
        "items": items,
        "created_at": now.isoformat(),
    }
    try:
        await db.invoices.insert_one(doc)
    except Exception as e:
        # duplicate — someone else created it first
        logger.warning("invoice insert duplicate: %s", e)
        return await db.invoices.find_one({"mollie_payment_id": payment_row["mollie_payment_id"]}, {"_id": 0})
    doc.pop("_id", None)
    # Emit a notification
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "workspace_id": workspace_id,
        "user_id": None,
        "type": "billing",
        "title": f"Invoice {invoice_number} — paid",
        "message": f"{doc['currency']} {doc['total']:.2f} received. PDF available.",
        "severity": "success",
        "read": False,
        "link": "/app/billing",
        "created_at": now.isoformat(),
    })
    return doc


async def _activate_subscription_from_first_payment(db, payment: dict):
    workspace_id = (payment.get("metadata") or {}).get("workspace_id")
    plan_id = (payment.get("metadata") or {}).get("plan")
    mandate_id = payment.get("mandateId")
    customer_id = payment.get("customerId")
    if not (workspace_id and plan_id and customer_id):
        return
    plan = await plans_get(plan_id)
    if not plan:
        return

    # Already active?
    existing = await db.subscriptions.find_one({"workspace_id": workspace_id})
    if existing and existing.get("mollie_subscription_id") and existing.get("plan") == plan_id and existing.get("status") == "active":
        return

    # If user is switching plans, cancel old subscription first
    if existing and existing.get("mollie_subscription_id") and existing.get("status") not in ("canceled",):
        try:
            await mollie.cancel_subscription(existing["mollie_customer_id"], existing["mollie_subscription_id"])
        except Exception as e:
            logger.warning("pre-switch cancel failed: %s", e)

    payload = {
        "amount": {"currency": "EUR", "value": f"{plan['price']:.2f}"},
        "interval": "1 month",
        "description": f"{plan['name']} plan subscription",
        "webhookUrl": os.environ.get("MOLLIE_WEBHOOK_URL"),
        "metadata": {"workspace_id": workspace_id, "plan": plan_id},
    }
    if mandate_id:
        payload["mandateId"] = mandate_id
    try:
        sub = await mollie.create_subscription(customer_id, payload=payload)
    except MollieError as e:
        logger.warning("subscription create failed: %s", e)
        return

    next_billing = sub.get("nextPaymentDate")
    await db.subscriptions.update_one(
        {"workspace_id": workspace_id},
        {"$set": {
            "id": (existing or {}).get("id") or str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "plan": plan_id,
            "status": "active",
            "mollie_subscription_id": sub["id"],
            "mollie_customer_id": customer_id,
            "mollie_mandate_id": mandate_id,
            "started_at": _now_iso(),
            "next_billing_at": next_billing,
        }},
        upsert=True,
    )
    await db.workspaces.update_one({"id": workspace_id}, {"$set": {"plan": plan_id}})


@router.post("/billing/mollie/webhook")
async def mollie_webhook(request: Request):
    """Mollie posts `id=<payment_id>` as form-urlencoded. We fetch the payment
    (authenticated with our API key) so we know the payload is trustworthy.
    Idempotent via payments.mollie_payment_id unique index."""
    db = get_db()
    form = await request.form()
    payment_id = form.get("id") or ""
    if not payment_id:
        # Mollie sometimes sends JSON too — best effort
        try:
            body = await request.json()
            payment_id = (body or {}).get("id")
        except Exception:
            pass
    if not payment_id:
        return PlainTextResponse("missing id", status_code=400)

    if not mollie.configured:
        return PlainTextResponse("ok", status_code=200)

    try:
        payment = await mollie.get_payment(payment_id)
    except MollieError as e:
        logger.warning("webhook fetch failed %s: %s", payment_id, e)
        # Return 200 so Mollie doesn't spam-retry; we log for investigation
        return PlainTextResponse("ignored", status_code=200)

    meta = payment.get("metadata") or {}
    workspace_id = meta.get("workspace_id")
    plan_id = meta.get("plan")
    status = payment.get("status")
    kind = meta.get("kind") or ("first" if payment.get("sequenceType") == "first" else "recurring")
    amount = float((payment.get("amount") or {}).get("value") or 0)
    method = payment.get("method")

    # Log
    await db.webhook_logs.insert_one({
        "id": str(uuid.uuid4()),
        "mollie_payment_id": payment_id,
        "status": status,
        "kind": kind,
        "workspace_id": workspace_id,
        "created_at": _now_iso(),
    })

    # If subscription (recurring) payment, workspace_id may not be in the payment meta.
    # Fallback: look up by customerId.
    if not workspace_id and payment.get("customerId"):
        mc = await db.mollie_customers.find_one({"mollie_customer_id": payment["customerId"]})
        workspace_id = (mc or {}).get("workspace_id")

    # Recurring subs payments also don't carry plan/vat metadata — reconstruct from latest known profile/subscription.
    if workspace_id and status == "paid":
        # Credit-pack payments: short-circuit — grant credits, store invoice
        if kind == "credit_pack":
            try:
                from services.credits import grant_credits, get_pack
                pack_id = meta.get("pack")
                credits_amount = int(meta.get("credits") or 0)
                if not credits_amount and pack_id:
                    pack = get_pack(pack_id)
                    credits_amount = (pack or {}).get("credits", 0)
                if credits_amount > 0:
                    await grant_credits(
                        workspace_id,
                        credits_amount,
                        reason=f"credit pack '{pack_id}' purchase",
                        type_="topup",
                        ref_id=payment_id,
                        ref_type="mollie_payment",
                    )
                await db.credit_pack_orders.update_one(
                    {"mollie_payment_id": payment_id},
                    {"$set": {"status": "paid", "paid_at": payment.get("paidAt") or _now_iso()}},
                )
            except Exception as e:
                logger.warning("credit pack grant failed for %s: %s", payment_id, e)
            return PlainTextResponse("ok", status_code=200)

        sub = await db.subscriptions.find_one({"workspace_id": workspace_id})
        profile = await db.billing_profiles.find_one({"workspace_id": workspace_id}, {"_id": 0}) or {}
        plan = await plans_get(plan_id or (sub or {}).get("plan") or "pro")
        # Grandfathered price — workspace may still be paying the old rate.
        effective_subtotal = float(plan["price"]) if plan else amount
        if plan:
            from services.grandfathering import effective_price
            effective_subtotal = await effective_price(workspace_id, plan)
        vat = compute_vat(
            country=profile.get("country", ""),
            is_business=bool(profile.get("is_business")),
            has_valid_vat_id=bool(profile.get("vat_id_valid")),
            home_cc=await effective_home_country(),
        )
        subtotal = effective_subtotal
        totals = compute_totals(subtotal=subtotal, vat_rate=vat["rate"])

        # Upsert payment row
        await db.payments.update_one(
            {"mollie_payment_id": payment_id},
            {"$set": {
                "id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "mollie_payment_id": payment_id,
                "mollie_customer_id": payment.get("customerId"),
                "mollie_subscription_id": payment.get("subscriptionId"),
                "kind": kind,
                "plan": plan["id"] if plan else plan_id,
                "status": "paid",
                "currency": "EUR",
                "method": method,
                "subtotal": totals["subtotal"],
                "vat_rate": vat["rate"],
                "vat_amount": totals["vat_amount"],
                "vat_note": vat["note"],
                "total": totals["total"],
                "paid_at": payment.get("paidAt") or _now_iso(),
                "updated_at": _now_iso(),
            }, "$setOnInsert": {"created_at": _now_iso()}},
            upsert=True,
        )
        payment_row = await db.payments.find_one({"mollie_payment_id": payment_id}, {"_id": 0})
        await _generate_invoice_for_payment(db, payment_row)

        # If first payment → create subscription
        if kind == "first":
            await _activate_subscription_from_first_payment(db, payment)

    elif workspace_id and status in ("failed", "canceled", "expired"):
        await db.payments.update_one(
            {"mollie_payment_id": payment_id},
            {"$set": {"status": status, "updated_at": _now_iso()}},
        )
        if kind == "first":
            await db.subscriptions.update_one(
                {"workspace_id": workspace_id},
                {"$set": {"status": status}},
            )
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "user_id": None,
                "type": "billing",
                "title": f"Payment {status}",
                "message": "Your plan upgrade payment was not completed. Try again from the Billing page.",
                "severity": "error",
                "read": False,
                "link": "/app/billing",
                "created_at": _now_iso(),
            })

    return PlainTextResponse("ok", status_code=200)


# ---------- Invoices ----------
@router.get("/billing/invoices")
async def list_invoices(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user, ["owner", "admin", "billing"])
    db = get_db()
    rows = await db.invoices.find(
        {"workspace_id": workspace_id}, {"_id": 0, "file_path": 0}
    ).sort("invoice_date", -1).to_list(100)
    for r in rows:
        r["pdf_url"] = f"/api/billing/invoices/{r['invoice_number']}/pdf"
    return rows


@router.get("/billing/invoices/{invoice_number}/pdf")
async def get_invoice_pdf(invoice_number: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    inv = await db.invoices.find_one({"invoice_number": invoice_number})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    await require_workspace_member(inv["workspace_id"], user, ["owner", "admin", "billing"])
    path = inv.get("file_path") or file_path_for(invoice_number)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="PDF missing")
    return FileResponse(path, filename=f"invoice_{invoice_number}.pdf", media_type="application/pdf")


# ---------- Admin utility: validate VAT ID on demand ----------
@router.get("/billing/vat/validate")
async def validate_vat(vat_id: str, request: Request):
    await get_current_user(request)
    return await validate_vies(vat_id)
