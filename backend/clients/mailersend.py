"""MailerSend transactional email client.

Async httpx wrapper for MailerSend's `/v1/email` endpoint. Credentials live
in `platform_settings` (admin-configurable, Fernet-encrypted), NOT env vars.

Public surface:
  * configured()           — bool: are API key + from_email both set?
  * send(...)              — POST /v1/email; returns {ok, message_id, error}
  * MailerSendError        — raised only when caller wants exceptions

Status handling:
  * 202 → success (X-Message-Id header)
  * 401 → invalid_key
  * 422 → validation
  * 429 → rate_limited (retry-after seconds)
  * 5xx → server_error
"""
import logging
from typing import Optional

import httpx

from crypto_utils import decrypt_token
from db import get_db

logger = logging.getLogger(__name__)

API_BASE = "https://api.mailersend.com/v1"


class MailerSendError(Exception):
    pass


async def _settings() -> Optional[dict]:
    """Pull MailerSend config from platform_settings, decrypt the API key."""
    doc = await get_db().platform_settings.find_one({"id": "platform-singleton"})
    if not doc:
        return None
    enc = doc.get("mailersend_api_key_enc")
    if not enc:
        return None
    try:
        api_key = decrypt_token(enc)
    except Exception as e:
        logger.warning("mailersend: decrypt api key failed: %s", e)
        return None
    from_email = doc.get("mailersend_from_email")
    from_name = doc.get("mailersend_from_name") or "DeployUnit"
    reply_to = doc.get("mailersend_reply_to") or None
    if not api_key or not from_email:
        return None
    return {
        "api_key": api_key,
        "from_email": from_email,
        "from_name": from_name,
        "reply_to": reply_to,
    }


async def configured() -> bool:
    return await _settings() is not None


async def send(
    *,
    to_email: str,
    to_name: Optional[str] = None,
    subject: str,
    html: Optional[str] = None,
    text: Optional[str] = None,
    tags: Optional[list[str]] = None,
    reply_to_email: Optional[str] = None,
) -> dict:
    """Send a transactional email. Returns dict — never raises.
    Shape: {ok: bool, message_id: str|None, error: str|None, status: str}"""
    cfg = await _settings()
    if not cfg:
        return {"ok": False, "status": "not_configured", "error": "MailerSend not configured", "message_id": None}
    if not html and not text:
        return {"ok": False, "status": "bad_input", "error": "html or text required", "message_id": None}

    payload: dict = {
        "from": {"email": cfg["from_email"], "name": cfg["from_name"]},
        "to": [{"email": to_email, **({"name": to_name} if to_name else {})}],
        "subject": subject,
    }
    if html:
        payload["html"] = html
    if text:
        payload["text"] = text
    if tags:
        payload["tags"] = tags
    reply = reply_to_email or cfg.get("reply_to")
    if reply:
        payload["reply_to"] = {"email": reply}

    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(
                f"{API_BASE}/email",
                json=payload,
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
    except httpx.TimeoutException:
        return {"ok": False, "status": "timeout", "error": "request timed out", "message_id": None}
    except Exception as e:
        return {"ok": False, "status": "network_error", "error": str(e)[:200], "message_id": None}

    if r.status_code == 202:
        return {"ok": True, "status": "queued", "error": None,
                "message_id": r.headers.get("x-message-id") or r.headers.get("X-Message-Id")}
    if r.status_code == 401:
        return {"ok": False, "status": "invalid_key", "error": "API key rejected", "message_id": None}
    if r.status_code == 422:
        return {"ok": False, "status": "validation", "error": r.text[:400], "message_id": None}
    if r.status_code == 429:
        return {"ok": False, "status": "rate_limited",
                "error": f"retry after {r.headers.get('retry-after','60')}s",
                "message_id": None}
    if 500 <= r.status_code < 600:
        return {"ok": False, "status": "server_error", "error": f"HTTP {r.status_code}", "message_id": None}
    return {"ok": False, "status": f"http_{r.status_code}", "error": r.text[:400], "message_id": None}
