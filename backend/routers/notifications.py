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



# ─────────────────────── User notification preferences ───────────────────────
from pydantic import BaseModel  # noqa: E402
from services.notifications_sms import (  # noqa: E402
    handle_twilio_status, send_alert, SUPPORTED_EVENT_TYPES,
)


class NotificationPrefsIn(BaseModel):
    phone_e164: str | None = None
    channels: dict  # {"sms": [...], "whatsapp": [...], "email": [...], "slack": [...], "discord": [...]}
    slack_webhook_url: str | None = None
    discord_webhook_url: str | None = None


@router.get("/notifications/prefs")
async def get_prefs(request: Request):
    user = await get_current_user(request)
    prefs = user.get("notification_prefs") or {}
    return {
        "phone_e164": prefs.get("phone_e164"),
        "channels": prefs.get("channels") or {},
        "slack_webhook_url": prefs.get("slack_webhook_url"),
        "discord_webhook_url": prefs.get("discord_webhook_url"),
        "supported_events": sorted(list(SUPPORTED_EVENT_TYPES)),
        "supported_channels": ["sms", "whatsapp", "email", "slack", "discord"],
    }


@router.put("/notifications/prefs")
async def set_prefs(payload: NotificationPrefsIn, request: Request):
    user = await get_current_user(request)
    db = get_db()
    phone = (payload.phone_e164 or "").strip()
    if phone and not phone.startswith("+"):
        raise HTTPException(status_code=400, detail="phone must be E.164 (start with +)")
    slack_url = (payload.slack_webhook_url or "").strip()
    if slack_url and not slack_url.startswith("https://hooks.slack.com/"):
        raise HTTPException(status_code=400, detail="slack webhook must start with https://hooks.slack.com/")
    discord_url = (payload.discord_webhook_url or "").strip()
    if discord_url and not discord_url.startswith("https://discord.com/api/webhooks/"):
        raise HTTPException(status_code=400, detail="discord webhook must start with https://discord.com/api/webhooks/")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"notification_prefs": {
            "phone_e164": phone or None,
            "channels": payload.channels or {},
            "slack_webhook_url": slack_url or None,
            "discord_webhook_url": discord_url or None,
        }}},
    )
    return {"ok": True}


class SendTestIn(BaseModel):
    workspace_id: str
    channel: str  # "sms" | "whatsapp" | "email" | "slack" | "discord"


@router.post("/notifications/test")
async def test_send(payload: SendTestIn, request: Request):
    """Fire a one-shot test alert to the current user via the chosen channel.
    Bypasses the preference matrix (the user explicitly chose), but still
    consumes credits like a real send."""
    user = await get_current_user(request)
    await require_workspace_member(payload.workspace_id, user)
    if payload.channel not in ("sms", "whatsapp", "email", "slack", "discord"):
        raise HTTPException(status_code=400, detail="channel must be sms, whatsapp, email, slack or discord")
    # Inject a temporary pref so send_alert dispatches this channel for the
    # synthetic event_type below.
    test_event = "deploy_succeeded"
    prefs = dict(user.get("notification_prefs") or {})
    channels = dict(prefs.get("channels") or {})
    existing = list(channels.get(payload.channel) or [])
    if test_event not in existing:
        existing.append(test_event)
    channels[payload.channel] = existing
    user_for_send = {**user, "notification_prefs": {**prefs, "channels": channels}}
    results = await send_alert(
        workspace_id=payload.workspace_id,
        user=user_for_send,
        event_type=test_event,
        title="DeployHub test",
        body="If you got this, your notification channel works.",
        channels=[payload.channel],
    )
    return {"results": results}


@router.post("/notifications/twilio/status")
async def twilio_status_webhook(request: Request):
    """Twilio posts URL-encoded form data here on status changes."""
    form = await request.form()
    payload = {k: v for k, v in form.items()}
    await handle_twilio_status(payload)
    return {"ok": True}
