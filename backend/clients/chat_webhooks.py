"""Slack + Discord incoming-webhook senders.

Both services accept a JSON POST to a per-user/per-channel webhook URL. No
auth keys to manage — the URL itself is the secret. We format the alert with
the event title + body and a colored accent.
"""
import logging
import httpx

logger = logging.getLogger(__name__)

# event_type → accent color (hex without #). Same palette as the UI.
_COLORS = {
    "deploy_failed":     "ef4444",  # red
    "deploy_succeeded":  "22c55e",  # green
    "app_down":          "ef4444",
    "app_recovered":     "22c55e",
    "build_warning":     "f59e0b",
    "domain_expiring":   "f59e0b",
    "credits_low":       "f59e0b",
}


def _accent_int(event_type: str) -> int:
    return int(_COLORS.get(event_type, "0ea5e9"), 16)


def _accent_hex(event_type: str) -> str:
    return "#" + _COLORS.get(event_type, "0ea5e9")


async def send_slack(*, webhook_url: str, title: str, body: str, event_type: str) -> None:
    """Slack incoming-webhook payload using a single attachment for color."""
    payload = {
        "attachments": [{
            "color": _accent_hex(event_type),
            "title": title,
            "text": body,
            "footer": f"DeployHub · {event_type}",
        }]
    }
    async with httpx.AsyncClient(timeout=10.0) as cli:
        r = await cli.post(webhook_url, json=payload)
    if r.status_code >= 400:
        raise RuntimeError(f"Slack webhook {r.status_code}: {r.text[:200]}")


async def send_discord(*, webhook_url: str, title: str, body: str, event_type: str) -> None:
    """Discord incoming-webhook payload using a single embed."""
    payload = {
        "embeds": [{
            "title": title,
            "description": body,
            "color": _accent_int(event_type),
            "footer": {"text": f"DeployHub · {event_type}"},
        }]
    }
    async with httpx.AsyncClient(timeout=10.0) as cli:
        r = await cli.post(webhook_url, json=payload)
    if r.status_code >= 400:
        raise RuntimeError(f"Discord webhook {r.status_code}: {r.text[:200]}")
