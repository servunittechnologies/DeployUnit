"""Notifications routes."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request

from db import get_db
from auth_utils import get_current_user, require_workspace_member

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def list_notifications(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    rows = await db.notifications.find(
        {"workspace_id": workspace_id}, {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)
    return rows


@router.post("/notifications/{notif_id}/read")
async def mark_read(notif_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    n = await db.notifications.find_one({"id": notif_id})
    if not n:
        raise HTTPException(status_code=404, detail="Not found")
    await require_workspace_member(n["workspace_id"], user)
    await db.notifications.update_one({"id": notif_id}, {"$set": {"read": True}})
    return {"ok": True}


@router.post("/notifications/read-all")
async def mark_all_read(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    await db.notifications.update_many(
        {"workspace_id": workspace_id, "read": False}, {"$set": {"read": True}}
    )
    return {"ok": True}
