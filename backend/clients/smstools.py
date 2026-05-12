"""Async SMSTools client — EU-based SMS gateway.

Replaces Twilio for SMS alerts. Same public surface (send_sms, configured,
cost_for_sms, SMSToolsError) so the notifications service barely had to
change. WhatsApp support was deliberately dropped — alerting now goes via
SMS / Email / Slack / Discord only.

API docs: https://www.smstools.com/en/sms-gateway-api
Endpoint: POST https://api.smsgatewayapi.com/v1/message/send
Auth:     headers X-Client-Id + X-Client-Secret
Body:     {message, to, sender, reference?, test?}
Response: {messageid, status, cost, balance}

Credentials live in `platform_settings` (admin-editable, Fernet-encrypted) —
never in env. Agencies can rotate without redeploys.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from db import get_db
from crypto_utils import decrypt_token

logger = logging.getLogger(__name__)

SMSTOOLS_API_BASE = "https://api.smsgatewayapi.com/v1"


class SMSToolsConfig:
    """Resolves SMSTools creds from platform_settings on every call (small
    DB read, async-safe). Returns None when nothing is configured so the
    caller can degrade gracefully (e.g. fall back to email)."""

    @staticmethod
    async def load() -> Optional[dict]:
        db = get_db()
        doc = await db.platform_settings.find_one({"id": "platform-singleton"}, {"_id": 0}) or {}
        client_id = doc.get("smstools_client_id")
        enc = doc.get("smstools_client_secret_enc")
        if not client_id or not enc:
            return None
        try:
            secret = decrypt_token(enc)
        except Exception:
            return None
        return {
            "client_id": client_id,
            "client_secret": secret,
            # Alphanumeric sender ID (≤11 chars) OR digits (≤14). EU best
            # practice: pre-register your brand name with SMSTools so
            # carriers accept it.
            "sender": (doc.get("smstools_sender_id") or "").strip() or None,
            "test_mode": bool(doc.get("smstools_test_mode")),
            # Webhook URL we tell SMSTools to call back with delivery status
            # so we can refund failed credits.
            "webhook_url": doc.get("smstools_webhook_url"),
        }


class SMSToolsError(Exception):
    pass


# Map of SMSTools numeric error codes → human messages.
# https://www.smstools.com/en/sms-gateway-api/handling_errors
_ERROR_MESSAGES = {
    103: "invalid recipient phone number",
    104: "invalid credentials",
    106: "invalid recipient phone number",
    108: "insufficient credits — top up SMSTools account",
    111: "invalid sender (≤11 alphanumeric or ≤14 digits)",
    118: "message body too long",
}


async def _post_message(cfg: dict, *, to: str, body: str, reference: str | None = None, _retry_no_sender: bool = False) -> dict:
    """Send an SMS via SMSTools. Returns the JSON response. Raises
    SMSToolsError on HTTP/business failures so the caller can decide to
    refund credits (handled upstream).

    Auto-retry quirk: if SMSTools rejects with code 111 (invalid sender) AND
    we did send a sender, transparently retry once without it. SMSTools then
    picks the route's default sender (works for most EU operators when the
    brand sender hasn't been pre-registered yet). This stops first-time
    setups from failing silently while the admin waits for sender approval.
    """
    # Strip the leading + so SMSTools accepts it (their API wants the digits
    # only, no '+'). E.164 → "+316XXXXXXXX" → "316XXXXXXXX".
    digits = (to or "").lstrip("+")
    if not digits:
        raise SMSToolsError("recipient is empty")

    payload: dict = {
        "message": body,
        "to": digits,
    }
    sender_to_use = None if _retry_no_sender else cfg.get("sender")
    if sender_to_use:
        payload["sender"] = sender_to_use
    if reference:
        payload["reference"] = reference[:255]
    if cfg.get("test_mode"):
        payload["test"] = True

    headers = {
        "X-Client-Id": cfg["client_id"],
        "X-Client-Secret": cfg["client_secret"],
        "Content-Type": "application/json",
    }
    url = f"{SMSTOOLS_API_BASE}/message/send"
    async with httpx.AsyncClient(timeout=12.0) as cli:
        r = await cli.post(url, json=payload, headers=headers)

    # Try to surface SMSTools' business errors verbatim.
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text[:200]}

    if r.status_code >= 400:
        code = data.get("code") or data.get("error_code")
        code_int = int(code) if (code and str(code).isdigit()) else None
        # Auto-fallback on "invalid sender" — try once more without one.
        if code_int == 111 and not _retry_no_sender and sender_to_use:
            logger.warning("smstools 111 (invalid sender %r) — retrying without sender", sender_to_use)
            return await _post_message(cfg, to=to, body=body, reference=reference, _retry_no_sender=True)
        hint = _ERROR_MESSAGES.get(code_int) if code_int else None
        # For 111, add the actionable next-steps so the toast is useful.
        if code_int == 111:
            hint = ("invalid sender — even after fallback. "
                    "Fix: in Admin → SMSTools, set Sender ID to (a) your own phone number digits-only "
                    "(e.g. 32475123456 — works immediately) OR (b) a pre-registered brand name "
                    "(register at smstools.com → Sender names → Add sender, 24-48h approval).")
        msg = data.get("message") or data.get("error") or r.text[:200]
        raise SMSToolsError(f"smstools {r.status_code}: {hint or msg}")

    # SMSTools sometimes returns 200 with an error payload — guard for that.
    if isinstance(data, dict) and data.get("error"):
        raise SMSToolsError(f"smstools: {data['error']}")
    return data


async def send_sms(to_e164: str, body: str, *, reference: str | None = None) -> dict:
    cfg = await SMSToolsConfig.load()
    if not cfg:
        raise SMSToolsError("SMSTools is not configured. Set Client ID + Secret in Admin → Platform Domain.")
    return await _post_message(cfg, to=to_e164, body=body, reference=reference)


async def configured() -> bool:
    cfg = await SMSToolsConfig.load()
    return cfg is not None


async def get_balance() -> Optional[float]:
    """Best-effort balance check for the admin dashboard. Returns None when
    not configured or the endpoint is unavailable."""
    cfg = await SMSToolsConfig.load()
    if not cfg:
        return None
    headers = {
        "X-Client-Id": cfg["client_id"],
        "X-Client-Secret": cfg["client_secret"],
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get(f"{SMSTOOLS_API_BASE}/balance", headers=headers)
        if r.status_code != 200:
            return None
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        # SMSTools balance response varies: try common shapes.
        for k in ("balance", "credit", "credits", "remaining"):
            v = (data or {}).get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
        return None
    except httpx.HTTPError:
        return None


def cost_for_sms(to_e164: str) -> int:
    """Credit cost for an SMS based on destination — identical to the old
    Twilio costing so existing wallets stay accurate."""
    p = (to_e164 or "").lstrip("+")
    eu_codes = ("31", "32", "33", "34", "39", "49", "41", "43", "45", "46", "47", "48", "30",
                "351", "352", "353", "358", "372", "370", "371")
    if any(p.startswith(c) for c in eu_codes):
        return 1
    if p.startswith("1"):  # US / Canada
        return 2
    return 2  # rest of world
