"""Project routes (agency grouping)."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from slugify import slugify

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from models import ProjectIn

router = APIRouter(tags=["projects"])


@router.get("/projects")
async def list_projects(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    rows = await db.projects.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(200)
    # attach app counts
    counts = {}
    pipeline = [
        {"$match": {"workspace_id": workspace_id}},
        {"$group": {"_id": "$project_id", "n": {"$sum": 1}}},
    ]
    async for r in db.apps.aggregate(pipeline):
        counts[r["_id"]] = r["n"]
    for r in rows:
        r["app_count"] = counts.get(r["id"], 0)
    return rows


@router.post("/projects")
async def create_project(payload: ProjectIn, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(payload.workspace_id, user, ["owner", "admin", "developer"])
    db = get_db()
    doc = {
        "id": str(uuid.uuid4()),
        "workspace_id": payload.workspace_id,
        "name": payload.name,
        "slug": slugify(payload.name),
        "description": payload.description or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.projects.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/projects/{project_id}")
async def get_project(project_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    await require_workspace_member(proj["workspace_id"], user)
    apps = await db.apps.find({"project_id": project_id}, {"_id": 0}).to_list(500)
    proj["apps"] = apps
    return proj


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    proj = await db.projects.find_one({"id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    await require_workspace_member(proj["workspace_id"], user, ["owner", "admin"])
    await db.apps.update_many({"project_id": project_id}, {"$set": {"project_id": None}})
    await db.projects.delete_one({"id": project_id})
    return {"deleted": True}
