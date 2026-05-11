"""Async Twilio client — Messages API only (no SDK, plain httpx).

Used to send SMS + WhatsApp alerts billed via the credit wallet. Keys come
from `platform_settings` (admin-editable, Fernet-encrypted) — never from env.
That way agencies can rotate credentials without redeploys.
"""
import os
import logging
from typing import Optional

import httpx

from db import get_db
from crypto_utils import decrypt_token

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


class TwilioConfig:
    """Resolves Twilio creds from platform_settings on every call (small DB
    read, async-safe). Returns None values when nothing is configured so the
    caller can degrade gracefully (e.g. fall back to email)."""

    @staticmethod
    async def load() -> Optional[dict]:
        db = get_db()
        doc = await db.platform_settings.find_one({"id": "platform-singleton"}, {"_id": 0}) or {}
        enc = doc.get("twilio_auth_token_enc")
        sid = doc.get("twilio_account_sid")
        if not sid or not enc:
            return None
        try:
            token = decrypt_token(enc)
        except Exception:
            return None
        return {
            "account_sid": sid,
            "auth_token": token,
            "messaging_service_sid": doc.get("twilio_messaging_service_sid"),
            "from_number": doc.get("twilio_from_number"),  # used when no Messaging Service
            "whatsapp_from": doc.get("twilio_whatsapp_from"),  # e.g. "whatsapp:+14155238886"
            "test_mode": bool(doc.get("twilio_test_mode")),
            "status_callback": doc.get("twilio_status_callback"),
        }


async def _post_message(cfg: dict, *, to: str, body: str, channel: str = "sms") -> dict:
    """Send a Messages.create POST. Returns Twilio response dict. Raises on
    network errors; caller decides whether to refund credits.
    """
    if cfg["test_mode"]:
        # Magic Twilio number that always 'sends' but doesn't actually deliver.
        # Useful for local dev. https://www.twilio.com/docs/iam/test-credentials
        pass
    data = {"To": to, "Body": body}
    if channel == "whatsapp":
        data["From"] = cfg["whatsapp_from"]
    elif cfg.get("messaging_service_sid"):
        data["MessagingServiceSid"] = cfg["messaging_service_sid"]
    else:
        data["From"] = cfg["from_number"]
    if cfg.get("status_callback"):
        data["StatusCallback"] = cfg["status_callback"]
    url = f"{TWILIO_API_BASE}/Accounts/{cfg['account_sid']}/Messages.json"
    async with httpx.AsyncClient(timeout=12.0) as cli:
        r = await cli.post(url, data=data, auth=(cfg["account_sid"], cfg["auth_token"]))
    if r.status_code >= 400:
        raise TwilioError(f"twilio {r.status_code}: {r.text[:200]}")
    return r.json()


class TwilioError(Exception):
    pass


async def send_sms(to_e164: str, body: str) -> dict:
    cfg = await TwilioConfig.load()
    if not cfg:
        raise TwilioError("Twilio is not configured. Set Account SID + Auth Token in Admin → Platform Domain.")
    return await _post_message(cfg, to=to_e164, body=body, channel="sms")


async def send_whatsapp(to_e164: str, body: str) -> dict:
    """to_e164 must be a real E.164 (e.g. +32475123456). We add the
    `whatsapp:` prefix automatically."""
    cfg = await TwilioConfig.load()
    if not cfg:
        raise TwilioError("Twilio is not configured.")
    if not cfg.get("whatsapp_from"):
        raise TwilioError("WhatsApp sender is not configured.")
    return await _post_message(cfg, to=f"whatsapp:{to_e164}", body=body, channel="whatsapp")


async def configured() -> bool:
    cfg = await TwilioConfig.load()
    return cfg is not None


def cost_for_sms(to_e164: str) -> int:
    """Credit cost for an SMS based on destination. Cheap heuristic — premium
    routes (US, intl) cost more than EU."""
    p = (to_e164 or "").lstrip("+")
    # EU dial codes (rough): 31 NL, 32 BE, 33 FR, 34 ES, 39 IT, 49 DE, 41 CH, 43 AT, 45 DK, 46 SE, 47 NO, 48 PL, 30 GR, 351 PT, 352 LU, 353 IE, 358 FI, 372 EE, 370 LT, 371 LV
    eu_codes = ("31", "32", "33", "34", "39", "49", "41", "43", "45", "46", "47", "48", "30",
                "351", "352", "353", "358", "372", "370", "371")
    if any(p.startswith(c) for c in eu_codes):
        return 1
    if p.startswith("1"):  # US / Canada
        return 2
    return 2  # rest of world


WHATSAPP_COST = 1  # 0.5 rounds to 1 — keep ints in our wallet
