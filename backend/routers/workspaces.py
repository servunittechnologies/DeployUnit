"""Workspace + member routes."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from slugify import slugify

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from models import WorkspaceIn, WorkspaceOut, WorkspaceMemberIn

router = APIRouter(tags=["workspaces"])


@router.get("/workspaces")
async def list_workspaces(request: Request):
    user = await get_current_user(request)
    db = get_db()
    memberships = await db.workspace_members.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).to_list(200)
    if not memberships:
        return []
    ws_ids = [m["workspace_id"] for m in memberships]
    workspaces = await db.workspaces.find(
        {"id": {"$in": ws_ids}}, {"_id": 0}
    ).to_list(200)
    role_map = {m["workspace_id"]: m["role"] for m in memberships}
    for w in workspaces:
        w["my_role"] = role_map.get(w["id"], "viewer")
    return workspaces


@router.post("/workspaces", response_model=WorkspaceOut)
async def create_workspace(payload: WorkspaceIn, request: Request):
    user = await get_current_user(request)
    db = get_db()
    ws_id = str(uuid.uuid4())
    base_slug = slugify(f"{payload.name}-{ws_id[:6]}")
    doc = {
        "id": ws_id,
        "name": payload.name,
        "slug": base_slug,
        "type": payload.type,
        "owner_id": user["id"],
        "plan": "hobby",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.workspaces.insert_one(doc)
    await db.workspace_members.insert_one(
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "user_id": user["id"],
            "role": "owner",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return doc


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.get("/workspaces/{workspace_id}/members")
async def list_members(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    members = await db.workspace_members.find(
        {"workspace_id": workspace_id}, {"_id": 0}
    ).to_list(200)
    user_ids = [m["user_id"] for m in members]
    users = await db.users.find(
        {"id": {"$in": user_ids}}, {"_id": 0, "password_hash": 0}
    ).to_list(200)
    user_map = {u["id"]: u for u in users}
    for m in members:
        u = user_map.get(m["user_id"], {})
        m["email"] = u.get("email")
        m["name"] = u.get("name")
    return members


@router.post("/workspaces/{workspace_id}/members")
async def add_member(workspace_id: str, payload: WorkspaceMemberIn, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user, ["owner", "admin"])
    db = get_db()
    target = await db.users.find_one({"email": payload.email.lower()})
    if not target:
        raise HTTPException(status_code=404, detail="User with that email does not have an account yet")
    existing = await db.workspace_members.find_one(
        {"workspace_id": workspace_id, "user_id": target["id"]}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already a member")
    member = {
        "id": str(uuid.uuid4()),
        "workspace_id": workspace_id,
        "user_id": target["id"],
        "role": payload.role,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.workspace_members.insert_one(member)
    return {**member, "email": target["email"], "name": target["name"]}


@router.delete("/workspaces/{workspace_id}/members/{user_id}")
async def remove_member(workspace_id: str, user_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user, ["owner", "admin"])
    db = get_db()
    ws = await db.workspaces.find_one({"id": workspace_id})
    if ws and ws["owner_id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot remove the workspace owner")
    res = await db.workspace_members.delete_one({"workspace_id": workspace_id, "user_id": user_id})
    return {"deleted": res.deleted_count}
