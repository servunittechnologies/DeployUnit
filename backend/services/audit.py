"""Centralised audit logging.

Append-only log of "who did what" across the platform. Used for compliance,
security investigations, and the Audit Log UI surface.

`log` is the only writer — every router/service that mutates business state
should call it. It writes async-fire-and-forget so callers don't pay latency.

Schema (db.audit_log):
  id, workspace_id (nullable for platform events), actor_id, actor_email,
  action (snake_case), resource_type, resource_id, meta (dict), ip, ua,
  created_at (ISO UTC).
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import Request

from db import get_db

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_ip(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    # Honor X-Forwarded-For from the ingress; fall back to request.client.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


async def _persist(doc: dict) -> None:
    try:
        await get_db().audit_log.insert_one(doc)
    except Exception as e:
        # Never block business code on a logging failure.
        logger.warning("audit log persist failed: %s", e)


def log(
    *,
    action: str,
    actor: Optional[dict] = None,
    workspace_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> None:
    """Fire-and-forget audit entry. Safe to call from anywhere."""
    doc = {
        "id": str(uuid.uuid4()),
        "workspace_id": workspace_id,
        "actor_id": (actor or {}).get("id"),
        "actor_email": (actor or {}).get("email"),
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "meta": meta or {},
        "ip": _client_ip(request),
        "ua": request.headers.get("user-agent")[:200] if request and request.headers.get("user-agent") else None,
        "created_at": _now_iso(),
    }
    asyncio.create_task(_persist(doc))
