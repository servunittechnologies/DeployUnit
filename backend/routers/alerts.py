"""Alert rules routes."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from models import AlertRuleIn

router = APIRouter(tags=["alerts"])


@router.get("/alerts")
async def list_rules(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    return await db.alert_rules.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(500)


@router.post("/alerts")
async def create_rule(payload: AlertRuleIn, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(payload.workspace_id, user, ["owner", "admin", "developer"])
    db = get_db()
    doc = {
        "id": str(uuid.uuid4()),
        **payload.model_dump(),
        "last_triggered_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.alert_rules.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/alerts/{rule_id}")
async def update_rule(rule_id: str, request: Request):
    user = await get_current_user(request)
    body = await request.json()
    db = get_db()
    rule = await db.alert_rules.find_one({"id": rule_id})
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await require_workspace_member(rule["workspace_id"], user, ["owner", "admin", "developer"])
    allowed = {k: v for k, v in body.items() if k in {"enabled", "threshold", "cooldown_seconds", "channels", "type"}}
    if allowed:
        await db.alert_rules.update_one({"id": rule_id}, {"$set": allowed})
    return await db.alert_rules.find_one({"id": rule_id}, {"_id": 0})


@router.delete("/alerts/{rule_id}")
async def delete_rule(rule_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    rule = await db.alert_rules.find_one({"id": rule_id})
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await require_workspace_member(rule["workspace_id"], user, ["owner", "admin", "developer"])
    await db.alert_rules.delete_one({"id": rule_id})
    return {"deleted": True}
