"""Billing routes — WHMCS hidden backend."""
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from models import CheckoutIn
from clients.whmcs import whmcs

router = APIRouter(tags=["billing"])


PLANS = [
    {
        "id": "hobby",
        "name": "Hobby",
        "price": 0,
        "currency": "USD",
        "interval": "month",
        "tagline": "For weekend projects.",
        "features": ["1 app", "1 custom domain", "Community support", "Basic monitoring"],
        "limits": {"apps": 1, "domains": 1, "team": 1},
        "highlight": False,
    },
    {
        "id": "pro",
        "name": "Pro",
        "price": 19,
        "currency": "USD",
        "interval": "month",
        "tagline": "For serious indies.",
        "features": ["10 apps", "5 custom domains", "Email alerts", "30s monitoring"],
        "limits": {"apps": 10, "domains": 5, "team": 3},
        "highlight": True,
    },
    {
        "id": "agency",
        "name": "Agency",
        "price": 99,
        "currency": "USD",
        "interval": "month",
        "tagline": "For studios shipping for clients.",
        "features": ["50 apps", "Unlimited domains", "Team roles", "Priority support", "Multiple projects"],
        "limits": {"apps": 50, "domains": 9999, "team": 25},
        "highlight": False,
    },
]


@router.get("/billing/plans")
async def list_plans():
    return PLANS


@router.get("/billing/subscription")
async def get_subscription(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    sub = await db.subscriptions.find_one({"workspace_id": workspace_id}, {"_id": 0})
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    return {
        "plan": ws.get("plan", "hobby") if ws else "hobby",
        "subscription": sub,
        "whmcs_configured": whmcs.configured,
    }


def _split_name(full: str) -> tuple[str, str]:
    parts = (full or "").strip().split()
    if not parts:
        return "User", "DeployHub"
    if len(parts) == 1:
        return parts[0], "User"
    return parts[0], " ".join(parts[1:])


@router.post("/billing/checkout")
async def checkout(payload: CheckoutIn, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(payload.workspace_id, user, ["owner", "admin", "billing"])
    db = get_db()
    plan = next((p for p in PLANS if p["id"] == payload.plan), None)
    if not plan:
        raise HTTPException(status_code=400, detail="Unknown plan")

    # 1. Ensure WHMCS client mapping exists
    mapping = await db.whmcs_mapping.find_one({"workspace_id": payload.workspace_id})
    whmcs_client_id = mapping.get("whmcs_client_id") if mapping else None
    invoice_link = None

    if plan["id"] == "hobby":
        # Free plan — no WHMCS interaction needed
        await db.workspaces.update_one(
            {"id": payload.workspace_id}, {"$set": {"plan": "hobby"}}
        )
        await db.subscriptions.update_one(
            {"workspace_id": payload.workspace_id},
            {
                "$set": {
                    "id": str(uuid.uuid4()),
                    "workspace_id": payload.workspace_id,
                    "plan": "hobby",
                    "status": "active",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            upsert=True,
        )
        return {"plan": "hobby", "status": "active", "invoice_link": None}

    if whmcs.configured and not whmcs_client_id:
        first, last = _split_name(user["name"])
        res = await whmcs.add_client(
            firstname=first, lastname=last, email=user["email"],
            password=str(uuid.uuid4())[:16],
        )
        if res.get("result") == "success" and res.get("clientid"):
            whmcs_client_id = int(res["clientid"])
            await db.whmcs_mapping.update_one(
                {"workspace_id": payload.workspace_id},
                {
                    "$set": {
                        "id": str(uuid.uuid4()),
                        "workspace_id": payload.workspace_id,
                        "whmcs_client_id": whmcs_client_id,
                        "whmcs_email": user["email"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
                upsert=True,
            )

    # 2. Create order if WHMCS configured
    invoice_id = None
    product_id = os.environ.get("WHMCS_DEFAULT_PRODUCT_ID")
    if whmcs.configured and whmcs_client_id:
        order_res = await whmcs.add_order(
            clientid=whmcs_client_id,
            pid=int(product_id) if product_id else None,
            billingcycle="monthly",
        )
        if order_res.get("result") == "success":
            invoice_id = order_res.get("invoiceid")
            if invoice_id:
                invoice_link = f"{whmcs.base}/viewinvoice.php?id={invoice_id}"

    sub = {
        "id": str(uuid.uuid4()),
        "workspace_id": payload.workspace_id,
        "plan": plan["id"],
        "status": "pending" if invoice_id else ("active" if whmcs.configured else "trial"),
        "whmcs_invoice_id": invoice_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.subscriptions.update_one(
        {"workspace_id": payload.workspace_id}, {"$set": sub}, upsert=True
    )
    await db.workspaces.update_one(
        {"id": payload.workspace_id},
        {"$set": {"plan": plan["id"]}},
    )
    await db.notifications.insert_one(
        {
            "id": str(uuid.uuid4()),
            "workspace_id": payload.workspace_id,
            "user_id": user["id"],
            "type": "billing",
            "title": f"Plan upgraded to {plan['name']}",
            "message": "Your invoice has been generated." if invoice_id else "Plan activated.",
            "severity": "success",
            "read": False,
            "link": invoice_link,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {
        "plan": plan["id"],
        "status": sub["status"],
        "invoice_id": invoice_id,
        "invoice_link": invoice_link,
        "whmcs_configured": whmcs.configured,
    }


@router.get("/billing/invoices")
async def list_invoices(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user, ["owner", "admin", "billing"])
    db = get_db()
    mapping = await db.whmcs_mapping.find_one({"workspace_id": workspace_id})
    if mapping and mapping.get("whmcs_client_id") and whmcs.configured:
        res = await whmcs.get_invoices(int(mapping["whmcs_client_id"]))
        if res.get("result") == "success":
            invoices = res.get("invoices", {}).get("invoice", [])
            # cache
            for inv in invoices:
                doc = {
                    "id": str(uuid.uuid4()),
                    "workspace_id": workspace_id,
                    "whmcs_invoice_id": str(inv.get("id")),
                    "number": str(inv.get("invoicenum") or inv.get("id")),
                    "amount": float(inv.get("total", 0) or 0),
                    "currency": inv.get("currencycode", "USD"),
                    "status": inv.get("status", "Unknown"),
                    "due_date": inv.get("duedate"),
                    "paid_date": inv.get("datepaid") if inv.get("datepaid") and inv.get("datepaid") != "0000-00-00" else None,
                    "items": [],
                    "link": f"{whmcs.base}/viewinvoice.php?id={inv.get('id')}",
                }
                await db.invoices_cache.update_one(
                    {"workspace_id": workspace_id, "whmcs_invoice_id": doc["whmcs_invoice_id"]},
                    {"$set": doc},
                    upsert=True,
                )
    cached = await db.invoices_cache.find(
        {"workspace_id": workspace_id}, {"_id": 0}
    ).sort("due_date", -1).to_list(50)
    return cached
