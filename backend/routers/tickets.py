"""Customer ticket system — users open tickets, admins reply.

Collections:
  tickets         {id, user_id, workspace_id?, subject, status, priority,
                   category, message_count, last_msg_at, last_msg_by,
                   last_msg_role, created_at, updated_at}
  ticket_messages {id, ticket_id, author_id, author_role (user|admin),
                   author_name, author_email, body, created_at}

User endpoints (authenticated):
  POST   /api/tickets                — create
  GET    /api/tickets                — list mine
  GET    /api/tickets/{id}           — detail + messages
  POST   /api/tickets/{id}/messages  — reply
  POST   /api/tickets/{id}/close     — close own ticket

Admin endpoints (role=admin):
  GET    /api/admin/tickets                — list all (filterable)
  GET    /api/admin/tickets/{id}           — detail + messages
  POST   /api/admin/tickets/{id}/messages  — reply as support
  PATCH  /api/admin/tickets/{id}           — change status / priority
  GET    /api/admin/tickets/stats          — open / awaiting / resolved counts
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Query
from pydantic import BaseModel, Field

from db import get_db
from auth_utils import get_current_user
from services.emails import (
    send_ticket_created,
    send_ticket_reply_to_user,
    send_ticket_reply_to_admins,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tickets"])

STATUSES = ("open", "awaiting_user", "awaiting_support", "resolved", "closed")
PRIORITIES = ("low", "normal", "high", "urgent")
CATEGORIES = ("deploy", "billing", "account", "technical", "feature_request", "other")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip(t: dict) -> dict:
    t.pop("_id", None)
    return t


async def _admin_emails() -> list[str]:
    """Return the email addresses of every active platform admin."""
    cur = get_db().users.find({"role": "admin"}, {"_id": 0, "email": 1})
    rows = await cur.to_list(50)
    return [r["email"] for r in rows if r.get("email")]


# ────────────────── Models ──────────────────
class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=10, max_length=8000)
    category: str = Field(default="other")
    priority: str = Field(default="normal")
    workspace_id: Optional[str] = None


class TicketMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class TicketUpdate(BaseModel):
    status: Optional[Literal["open", "awaiting_user", "awaiting_support", "resolved", "closed"]] = None
    priority: Optional[Literal["low", "normal", "high", "urgent"]] = None
    category: Optional[str] = None


# ────────────────── User endpoints ──────────────────
@router.post("/tickets")
async def create_ticket(payload: TicketCreate, request: Request, background: BackgroundTasks):
    user = await get_current_user(request)
    if payload.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown category")
    if payload.priority not in PRIORITIES:
        raise HTTPException(status_code=400, detail="Unknown priority")
    db = get_db()
    now = _now()
    ticket = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_email": user.get("email"),
        "user_name": user.get("name") or user.get("email"),
        "workspace_id": payload.workspace_id,
        "subject": payload.subject.strip(),
        "status": "open",
        "priority": payload.priority,
        "category": payload.category,
        "message_count": 1,
        "last_msg_at": now,
        "last_msg_by": user["id"],
        "last_msg_role": "user",
        "created_at": now,
        "updated_at": now,
    }
    msg = {
        "id": str(uuid.uuid4()),
        "ticket_id": ticket["id"],
        "author_id": user["id"],
        "author_role": "user",
        "author_name": user.get("name") or user.get("email"),
        "author_email": user.get("email"),
        "body": payload.message.strip(),
        "created_at": now,
    }
    await db.tickets.insert_one(ticket)
    await db.ticket_messages.insert_one(msg)
    # Notify admins via email — fire-and-forget
    admins = await _admin_emails()
    if admins:
        background.add_task(
            send_ticket_created,
            ticket=_strip(dict(ticket)),
            message_body=payload.message.strip(),
            admin_recipients=admins,
        )
    return _strip(ticket)


@router.get("/tickets")
async def list_my_tickets(request: Request):
    user = await get_current_user(request)
    db = get_db()
    cur = db.tickets.find({"user_id": user["id"]}, {"_id": 0}).sort("last_msg_at", -1).limit(200)
    rows = await cur.to_list(200)
    return {"tickets": rows, "total": len(rows)}


async def _ensure_access(ticket_id: str, user: dict) -> dict:
    db = get_db()
    t = await db.tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if user.get("role") != "admin" and t["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your ticket")
    return t


@router.get("/tickets/{ticket_id}")
async def ticket_detail(ticket_id: str, request: Request):
    user = await get_current_user(request)
    ticket = await _ensure_access(ticket_id, user)
    db = get_db()
    cur = db.ticket_messages.find({"ticket_id": ticket_id}, {"_id": 0}).sort("created_at", 1)
    msgs = await cur.to_list(500)
    return {"ticket": ticket, "messages": msgs}


@router.post("/tickets/{ticket_id}/messages")
async def add_message(ticket_id: str, payload: TicketMessageIn, request: Request, background: BackgroundTasks):
    user = await get_current_user(request)
    ticket = await _ensure_access(ticket_id, user)
    if ticket["status"] == "closed":
        raise HTTPException(status_code=409, detail="Ticket is closed. Open a new one.")
    db = get_db()
    now = _now()
    is_admin = user.get("role") == "admin"
    role = "admin" if is_admin else "user"
    msg = {
        "id": str(uuid.uuid4()),
        "ticket_id": ticket_id,
        "author_id": user["id"],
        "author_role": role,
        "author_name": user.get("name") or user.get("email"),
        "author_email": user.get("email"),
        "body": payload.body.strip(),
        "created_at": now,
    }
    await db.ticket_messages.insert_one(msg)
    # Update ticket meta + flip status
    new_status = "awaiting_support" if role == "user" else "awaiting_user"
    if ticket["status"] in ("resolved", "closed") and role == "user":
        new_status = "awaiting_support"
    await db.tickets.update_one(
        {"id": ticket_id},
        {"$set": {
            "last_msg_at": now,
            "last_msg_by": user["id"],
            "last_msg_role": role,
            "updated_at": now,
            "status": new_status,
        }, "$inc": {"message_count": 1}},
    )
    msg.pop("_id", None)
    # Send email notification — fire-and-forget
    fresh = await db.tickets.find_one({"id": ticket_id}, {"_id": 0})
    if fresh:
        body_text = payload.body.strip()
        if role == "admin":
            background.add_task(send_ticket_reply_to_user, ticket=fresh, message_body=body_text)
        else:
            admins = await _admin_emails()
            # Don't email the author back to themselves if the author is an admin replying as user
            recipients = [a for a in admins if a != fresh.get("user_email")]
            if recipients:
                background.add_task(
                    send_ticket_reply_to_admins,
                    ticket=fresh, message_body=body_text,
                    admin_recipients=recipients,
                )
    return msg


@router.post("/tickets/{ticket_id}/close")
async def close_my_ticket(ticket_id: str, request: Request):
    user = await get_current_user(request)
    await _ensure_access(ticket_id, user)
    db = get_db()
    await db.tickets.update_one(
        {"id": ticket_id},
        {"$set": {"status": "closed", "updated_at": _now()}},
    )
    return {"ok": True}


# ────────────────── Admin endpoints ──────────────────
async def _require_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    return user


@router.get("/admin/tickets")
async def admin_list_tickets(
    request: Request,
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    await _require_admin(request)
    db = get_db()
    flt: dict = {}
    if status: flt["status"] = status
    if priority: flt["priority"] = priority
    if category: flt["category"] = category
    if q:
        flt["$or"] = [
            {"subject": {"$regex": q, "$options": "i"}},
            {"user_email": {"$regex": q, "$options": "i"}},
            {"user_name": {"$regex": q, "$options": "i"}},
        ]
    total = await db.tickets.count_documents(flt)
    cur = db.tickets.find(flt, {"_id": 0}).sort("last_msg_at", -1).skip(offset).limit(limit)
    rows = await cur.to_list(limit)
    return {"tickets": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/admin/tickets/stats")
async def admin_ticket_stats(request: Request):
    await _require_admin(request)
    db = get_db()
    pipeline = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    rows = await db.tickets.aggregate(pipeline).to_list(20)
    by_status = {r["_id"]: r["n"] for r in rows}
    return {
        "open":               by_status.get("open", 0),
        "awaiting_support":   by_status.get("awaiting_support", 0),
        "awaiting_user":      by_status.get("awaiting_user", 0),
        "resolved":           by_status.get("resolved", 0),
        "closed":             by_status.get("closed", 0),
        "total":              sum(by_status.values()),
        "needs_attention":    by_status.get("open", 0) + by_status.get("awaiting_support", 0),
    }


@router.get("/admin/tickets/{ticket_id}")
async def admin_ticket_detail(ticket_id: str, request: Request):
    await _require_admin(request)
    db = get_db()
    t = await db.tickets.find_one({"id": ticket_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    cur = db.ticket_messages.find({"ticket_id": ticket_id}, {"_id": 0}).sort("created_at", 1)
    msgs = await cur.to_list(500)
    return {"ticket": t, "messages": msgs}


@router.post("/admin/tickets/{ticket_id}/messages")
async def admin_add_message(ticket_id: str, payload: TicketMessageIn, request: Request, background: BackgroundTasks):
    await _require_admin(request)
    return await add_message(ticket_id, payload, request, background)


@router.patch("/admin/tickets/{ticket_id}")
async def admin_update_ticket(ticket_id: str, payload: TicketUpdate, request: Request):
    await _require_admin(request)
    updates: dict = {}
    if payload.status is not None:
        if payload.status not in STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        updates["status"] = payload.status
    if payload.priority is not None:
        if payload.priority not in PRIORITIES:
            raise HTTPException(status_code=400, detail="Invalid priority")
        updates["priority"] = payload.priority
    if payload.category is not None:
        if payload.category not in CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        updates["category"] = payload.category
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    updates["updated_at"] = _now()
    db = get_db()
    res = await db.tickets.update_one({"id": ticket_id}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")
    t = await db.tickets.find_one({"id": ticket_id}, {"_id": 0})
    return t
