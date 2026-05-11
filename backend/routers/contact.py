"""Public contact form — saves messages to MongoDB, optionally pings admin.

`POST /api/contact` is public (no auth) but lightly rate-limited per IP.
"""
import re
import uuid
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from db import get_db
from auth_utils import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["contact"])

KINDS = {"general", "sales", "support", "press", "partnership"}


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    company: str | None = Field(default=None, max_length=120)
    kind: str = Field(default="general")
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=10, max_length=4000)


@router.post("/contact")
async def submit_contact(payload: ContactIn, request: Request):
    if payload.kind not in KINDS:
        raise HTTPException(status_code=400, detail="Unknown contact kind.")
    db = get_db()
    xff = request.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "?")
    now = datetime.now(timezone.utc)
    # Light rate-limit — max 5 submissions per IP per hour
    since = (now - timedelta(hours=1)).isoformat()
    recent = await db.contact_messages.count_documents({"source_ip": ip, "created_at": {"$gte": since}})
    if recent >= 5:
        raise HTTPException(status_code=429, detail="Too many messages. Try again in an hour.")

    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name.strip(),
        "email": str(payload.email).strip().lower(),
        "company": (payload.company or "").strip() or None,
        "kind": payload.kind,
        "subject": payload.subject.strip(),
        "message": payload.message.strip(),
        "source_ip": ip,
        "user_agent": (request.headers.get("user-agent") or "")[:300],
        "status": "new",
        "created_at": now.isoformat(),
    }
    # Attach logged-in user_id if applicable
    try:
        u = await get_current_user(request)
        doc["user_id"] = u.get("id")
    except Exception:
        pass
    await db.contact_messages.insert_one(doc)
    logger.info("contact: new %s message from %s", doc["kind"], doc["email"])
    return {"ok": True, "id": doc["id"]}


@router.get("/admin/contact")
async def admin_list(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    db = get_db()
    cur = db.contact_messages.find({}, {"_id": 0}).sort("created_at", -1).limit(500)
    return await cur.to_list(500)
