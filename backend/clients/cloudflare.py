"""Cloudflare API client — DNS records only.

Used for the "free subdomain per app" feature. Credentials come from
`platform_settings` (admin-editable, Fernet-encrypted), never from env.
Failures are logged + returned as None so deployment is never blocked.
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CF_API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareError(Exception):
    pass


async def _request(method: str, path: str, *, token: str, json: Optional[dict] = None) -> Optional[dict]:
    """Authenticated Cloudflare API call. Returns parsed `result` on success,
    None on failure (logged)."""
    url = f"{CF_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.request(method, url, headers=headers, json=json)
        if r.status_code >= 400:
            logger.warning("Cloudflare %s %s -> %s %s", method, path, r.status_code, r.text[:300])
            return None
        body = r.json()
        if not body.get("success"):
            logger.warning("Cloudflare %s %s api-error: %s", method, path, body.get("errors"))
            return None
        return body.get("result")
    except Exception as e:
        logger.warning("Cloudflare %s %s failed: %s", method, path, e)
        return None


async def create_dns_record(
    *,
    token: str,
    zone_id: str,
    name: str,
    record_type: str,
    content: str,
    proxied: bool = False,
    ttl: int = 1,  # 1 = automatic
) -> Optional[dict]:
    """Create an A / AAAA / CNAME record. Returns {id, name, ...} on success."""
    payload = {
        "type": record_type,
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied,
    }
    return await _request("POST", f"/zones/{zone_id}/dns_records", token=token, json=payload)


async def delete_dns_record(*, token: str, zone_id: str, record_id: str) -> bool:
    res = await _request("DELETE", f"/zones/{zone_id}/dns_records/{record_id}", token=token)
    return res is not None
