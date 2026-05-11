"""Audit log read API.

Returns the audit log for a workspace (owner/admin only) or the platform-wide
log (platform admin only).
"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional

from db import get_db
from auth_utils import get_current_user, require_workspace_member

router = APIRouter(tags=["audit"])


@router.get("/audit-log")
async def list_audit(
    request: Request,
    workspace_id: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    before: Optional[str] = Query(default=None, description="ISO timestamp for cursor pagination"),
):
    user = await get_current_user(request)
    q: dict = {}
    if workspace_id:
        # Owner/admin of the workspace can read its audit log
        await require_workspace_member(workspace_id, user, ["owner", "admin"])
        q["workspace_id"] = workspace_id
    else:
        # Platform-wide audit log: only platform admins
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Platform audit log requires admin role")
    if action:
        q["action"] = action
    if actor_id:
        q["actor_id"] = actor_id
    if before:
        q["created_at"] = {"$lt": before}

    db = get_db()
    rows = (
        await db.audit_log.find(q, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    return {"entries": rows, "limit": limit}


@router.get("/audit-log/actions")
async def list_actions(request: Request, workspace_id: Optional[str] = Query(default=None)):
    """Distinct action names — drives the filter dropdown in the UI."""
    user = await get_current_user(request)
    q: dict = {}
    if workspace_id:
        await require_workspace_member(workspace_id, user, ["owner", "admin"])
        q["workspace_id"] = workspace_id
    elif user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    actions = await get_db().audit_log.distinct("action", q)
    return {"actions": sorted(actions)}
