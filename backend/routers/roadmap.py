"""Roadmap waitlist — public signups for upcoming features.

Stores `{email, feature, source, ip, ts}` so the platform admin can
ping their highest-intent leads on each launch.
"""
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from db import get_db
from auth_utils import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["roadmap"])

# Whitelist of features users can sign up for. Keep keys stable — they
# index waitlist segments in MongoDB and on the admin export.
KNOWN_FEATURES = {
    # Analytics & Insights
    "heatmaps":   "Native heatmaps & session replays",
    # Developer experience
    "branching":  "Database branching",
    "copilot":    "AI Code Co-pilot",
    "visualdiff": "Visual deploy diffs",
    "api":        "Developers API",
    # Business tools
    "reports":    "White-label client reports",
    # Infrastructure
    "mailserver": "Mailserver hosting",
    "dns":        "DNS Manager",
}


class WaitlistSignup(BaseModel):
    feature: str
    email: EmailStr


@router.get("/roadmap/features")
async def list_features():
    """Public — used by both the customer roadmap page and the marketing site
    to show what's in flight."""
    db = get_db()
    out = []
    for key, label in KNOWN_FEATURES.items():
        count = await db.roadmap_waitlist.count_documents({"feature": key})
        out.append({"id": key, "label": label, "waitlist_count": count})
    return out


@router.post("/roadmap/waitlist")
async def signup(payload: WaitlistSignup, request: Request):
    if payload.feature not in KNOWN_FEATURES:
        raise HTTPException(status_code=400, detail="Unknown feature")
    db = get_db()
    email = str(payload.email).strip().lower()
    xff = request.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "?")
    # Idempotent: same email+feature pair = no-op.
    existing = await db.roadmap_waitlist.find_one(
        {"feature": payload.feature, "email": email},
        {"_id": 0, "id": 1},
    )
    if existing:
        return {"ok": True, "already_signed_up": True}
    doc = {
        "id": str(uuid.uuid4()),
        "feature": payload.feature,
        "email": email,
        "source_ip": ip,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Try to attach the logged-in user if we have one (cookie-based auth).
    try:
        user = await get_current_user(request)
        doc["user_id"] = user.get("id")
    except Exception:
        pass
    await db.roadmap_waitlist.insert_one(doc)
    return {"ok": True, "already_signed_up": False}


@router.get("/admin/roadmap/waitlist")
async def admin_list(request: Request, feature: Optional[str] = None):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    db = get_db()
    q = {}
    if feature:
        if feature not in KNOWN_FEATURES:
            raise HTTPException(status_code=400, detail="Unknown feature")
        q["feature"] = feature
    cur = db.roadmap_waitlist.find(q, {"_id": 0}).sort("created_at", -1).limit(500)
    rows = await cur.to_list(500)
    by_feature: dict[str, list] = {k: [] for k in KNOWN_FEATURES}
    for r in rows:
        by_feature.setdefault(r["feature"], []).append(r)
    return {"features": KNOWN_FEATURES, "rows": rows, "by_feature": by_feature}
