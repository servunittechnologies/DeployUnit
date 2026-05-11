"""User profile + change password."""
from fastapi import APIRouter, HTTPException, Request

from db import get_db
from auth_utils import get_current_user, hash_password, verify_password
from models import UserUpdateIn, ChangePasswordIn
from clients.coolify import coolify
from clients.whmcs import whmcs
from clients.twilio import configured as twilio_configured

router = APIRouter(tags=["settings"])


@router.patch("/users/me")
async def update_me(payload: UserUpdateIn, request: Request):
    user = await get_current_user(request)
    db = get_db()
    update = {}
    if payload.name is not None:
        update["name"] = payload.name.strip()
    if update:
        await db.users.update_one({"id": user["id"]}, {"$set": update})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    return fresh


@router.post("/users/me/change-password")
async def change_password(payload: ChangePasswordIn, request: Request):
    user = await get_current_user(request)
    db = get_db()
    full = await db.users.find_one({"id": user["id"]})
    if not full or not verify_password(payload.current_password, full["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one(
        {"id": user["id"]}, {"$set": {"password_hash": hash_password(payload.new_password)}}
    )
    return {"ok": True}


@router.get("/integrations/health")
async def integrations_health(request: Request):
    await get_current_user(request)
    tw_ok = await twilio_configured()
    return {
        "coolify": await coolify.health(),
        "whmcs": await whmcs.health(),
        "twilio": {"configured": tw_ok, "ok": tw_ok},
    }
