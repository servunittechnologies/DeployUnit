"""SMS + WhatsApp notification dispatcher with credit accounting.

Single entrypoint `send_alert(workspace_id, user, channels, title, body)` —
fans out to enabled channels, deducts credits, logs to
`notification_sends`. If Twilio rejects (network/account error) the credit
is refunded so customers don't pay for our outages.

User preferences live on `users.notification_prefs`:
    {
        "phone_e164": "+32475123456",
        "channels": {
            "sms": ["deploy_failed", "app_down"],
            "whatsapp": ["app_down"],
            "email": ["deploy_failed", "deploy_succeeded", "app_down"]
        }
    }
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from db import get_db
from services.credits import consume_credits, grant_credits
from clients.twilio import (
    send_sms, send_whatsapp, configured as twilio_configured,
    cost_for_sms, WHATSAPP_COST, TwilioError,
)

logger = logging.getLogger(__name__)


SUPPORTED_EVENT_TYPES = {
    "deploy_failed", "deploy_succeeded",
    "app_down", "app_recovered",
    "build_warning", "domain_expiring",
    "credits_low",
}

# Single source of truth for the channel list. Mirrored in
# routers/notifications.py::get_prefs.supported_channels — keep in sync.
SUPPORTED_CHANNELS = ("sms", "whatsapp", "email", "slack", "discord")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _log_send(*, workspace_id: str, user_id: str, channel: str, event_type: str,
                    to: str, body: str, status: str, cost: int,
                    twilio_sid: Optional[str] = None, error: Optional[str] = None) -> str:
    db = get_db()
    send_id = str(uuid.uuid4())
    await db.notification_sends.insert_one({
        "id": send_id,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "channel": channel,
        "event_type": event_type,
        "to": to,
        "body": body[:500],
        "status": status,
        "cost_credits": cost,
        "twilio_sid": twilio_sid,
        "error": (error or "")[:300] if error else None,
        "created_at": _now_iso(),
    })
    return send_id


async def send_alert(
    *,
    workspace_id: str,
    user: dict,
    event_type: str,
    title: str,
    body: str,
    channels: Optional[list[str]] = None,
) -> list[dict]:
    """Dispatch an alert to user's enabled channels. Returns list of per-
    channel results: [{channel, status, cost, error}]. Never raises — all
    failures are logged so the caller can keep moving.
    """
    if event_type not in SUPPORTED_EVENT_TYPES:
        logger.warning("send_alert: unsupported event_type=%s", event_type)
    prefs = user.get("notification_prefs") or {}
    phone = prefs.get("phone_e164")
    pref_channels = prefs.get("channels") or {}

    # Effective channel list — if caller passed channels, intersect with prefs.
    available = []
    for ch in SUPPORTED_CHANNELS:
        if event_type in (pref_channels.get(ch) or []):
            if channels is None or ch in channels:
                available.append(ch)
    if not available:
        return []

    sms_message = f"[{title}] {body}" if title else body
    results = []
    twilio_ok = await twilio_configured()

    for ch in available:
        if ch == "sms":
            if not phone or not twilio_ok:
                await _log_send(
                    workspace_id=workspace_id, user_id=user["id"], channel="sms",
                    event_type=event_type, to=phone or "—", body=sms_message,
                    status="skipped", cost=0,
                    error="no phone" if not phone else "twilio not configured",
                )
                results.append({"channel": "sms", "status": "skipped"})
                continue
            cost = cost_for_sms(phone)
            try:
                await consume_credits(
                    workspace_id, cost,
                    reason=f"SMS alert: {event_type}",
                    ref_type="sms",
                )
            except Exception as e:
                await _log_send(
                    workspace_id=workspace_id, user_id=user["id"], channel="sms",
                    event_type=event_type, to=phone, body=sms_message,
                    status="insufficient_credits", cost=0,
                    error=str(e)[:200],
                )
                results.append({"channel": "sms", "status": "insufficient_credits"})
                continue
            try:
                resp = await send_sms(phone, sms_message)
                await _log_send(
                    workspace_id=workspace_id, user_id=user["id"], channel="sms",
                    event_type=event_type, to=phone, body=sms_message,
                    status="sent", cost=cost, twilio_sid=resp.get("sid"),
                )
                results.append({"channel": "sms", "status": "sent", "cost": cost})
            except TwilioError as e:
                # Refund — our integration failed, not the customer's fault.
                await grant_credits(
                    workspace_id, cost,
                    reason=f"refund: SMS {event_type} failed",
                    type_="refund",
                )
                await _log_send(
                    workspace_id=workspace_id, user_id=user["id"], channel="sms",
                    event_type=event_type, to=phone, body=sms_message,
                    status="failed", cost=0, error=str(e),
                )
                results.append({"channel": "sms", "status": "failed", "error": str(e)})

        elif ch == "whatsapp":
            if not phone or not twilio_ok:
                await _log_send(
                    workspace_id=workspace_id, user_id=user["id"], channel="whatsapp",
                    event_type=event_type, to=phone or "—", body=sms_message,
                    status="skipped", cost=0,
                    error="no phone" if not phone else "twilio not configured",
                )
                results.append({"channel": "whatsapp", "status": "skipped"})
                continue
            cost = WHATSAPP_COST
            try:
                await consume_credits(workspace_id, cost,
                                      reason=f"WhatsApp alert: {event_type}",
                                      ref_type="whatsapp")
            except Exception:
                results.append({"channel": "whatsapp", "status": "insufficient_credits"})
                continue
            try:
                resp = await send_whatsapp(phone, sms_message)
                await _log_send(
                    workspace_id=workspace_id, user_id=user["id"], channel="whatsapp",
                    event_type=event_type, to=phone, body=sms_message,
                    status="sent", cost=cost, twilio_sid=resp.get("sid"),
                )
                results.append({"channel": "whatsapp", "status": "sent", "cost": cost})
            except TwilioError as e:
                await grant_credits(workspace_id, cost,
                                    reason=f"refund: WhatsApp {event_type} failed",
                                    type_="refund")
                await _log_send(
                    workspace_id=workspace_id, user_id=user["id"], channel="whatsapp",
                    event_type=event_type, to=phone, body=sms_message,
                    status="failed", cost=0, error=str(e),
                )
                results.append({"channel": "whatsapp", "status": "failed", "error": str(e)})

        elif ch == "email":
            # Email is free + still mocked — the in-app notifications collection
            # already covers most needs. Real email integration is P1 backlog.
            db = get_db()
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user["id"],
                "workspace_id": workspace_id,
                "title": title,
                "message": body,
                "event_type": event_type,
                "channel": "email",
                "created_at": _now_iso(),
                "read": False,
            })
            results.append({"channel": "email", "status": "queued", "cost": 0})

        elif ch in ("slack", "discord"):
            # Webhook-based — free for the user, no Twilio. We just POST to the
            # user-provided incoming webhook URL.
            webhook = (user.get("notification_prefs") or {}).get(f"{ch}_webhook_url")
            if not webhook:
                await _log_send(
                    workspace_id=workspace_id, user_id=user["id"], channel=ch,
                    event_type=event_type, to="—", body=body,
                    status="skipped", cost=0, error=f"no {ch} webhook URL",
                )
                results.append({"channel": ch, "status": "skipped"})
                continue
            try:
                from clients.chat_webhooks import send_slack, send_discord
                sender = send_slack if ch == "slack" else send_discord
                await sender(webhook_url=webhook, title=title, body=body, event_type=event_type)
                await _log_send(
                    workspace_id=workspace_id, user_id=user["id"], channel=ch,
                    event_type=event_type, to=webhook[:60], body=body,
                    status="sent", cost=0,
                )
                results.append({"channel": ch, "status": "sent", "cost": 0})
            except Exception as e:
                await _log_send(
                    workspace_id=workspace_id, user_id=user["id"], channel=ch,
                    event_type=event_type, to=webhook[:60], body=body,
                    status="failed", cost=0, error=str(e)[:200],
                )
                results.append({"channel": ch, "status": "failed", "error": str(e)[:200]})

    return results


async def handle_twilio_status(payload: dict) -> None:
    """Webhook hook — Twilio posts delivery status. Refund credits on permanent
    failures (undelivered, failed). Status values: queued, sending, sent,
    delivered, undelivered, failed.
    """
    sid = payload.get("MessageSid") or payload.get("SmsSid")
    status = (payload.get("MessageStatus") or "").lower()
    if not sid:
        return
    db = get_db()
    send = await db.notification_sends.find_one({"twilio_sid": sid}, {"_id": 0})
    if not send:
        return
    new_status = status
    await db.notification_sends.update_one(
        {"twilio_sid": sid},
        {"$set": {"status": new_status, "updated_at": _now_iso()}},
    )
    if status in ("undelivered", "failed") and send.get("cost_credits", 0) > 0:
        # Refund — message never reached the recipient.
        try:
            await grant_credits(
                send["workspace_id"],
                int(send["cost_credits"]),
                reason=f"refund: {send['channel']} {status} for {send.get('event_type')}",
                type_="refund",
                ref_id=sid,
                ref_type="twilio_status",
            )
            await db.notification_sends.update_one(
                {"twilio_sid": sid},
                {"$set": {"refunded": True}},
            )
        except Exception as e:
            logger.warning("refund failed for %s: %s", sid, e)
