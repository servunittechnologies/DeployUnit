"""Deployment routes."""
from fastapi import APIRouter, HTTPException, Request

from db import get_db
from auth_utils import get_current_user, require_workspace_member

router = APIRouter(tags=["deployments"])


@router.get("/apps/{app_id}/deployments")
async def list_deployments(app_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    rows = await db.deployments.find(
        {"app_id": app_id}, {"_id": 0}
    ).sort("started_at", -1).to_list(50)
    return rows


@router.get("/deployments/{deployment_id}")
async def get_deployment(deployment_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    d = await db.deployments.find_one({"id": deployment_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")
    await require_workspace_member(d["workspace_id"], user)
    return d


@router.get("/deployments/{deployment_id}/logs")
async def get_deployment_logs(deployment_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    d = await db.deployments.find_one({"id": deployment_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")
    await require_workspace_member(d["workspace_id"], user)
    return {"logs": d.get("logs", []), "status": d["status"]}
