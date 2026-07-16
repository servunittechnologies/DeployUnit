"""Workspace + member routes."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slugify import slugify

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from models import WorkspaceIn, WorkspaceOut, WorkspaceMemberIn
from services.plans import workspace_plan, workspace_usage
from services.credits import get_balance as credits_balance
from services.grandfathering import effective_price, upcoming_change
from services.billing_guard import billing_source

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
    # Enforce plan `workspaces` cap (account-level).
    from services.plans import user_plan, account_usage, list_plans
    plan = await user_plan(user["id"])
    cap = (plan.get("limits") or {}).get("workspaces")
    if cap is not None and cap >= 0:
        usage = await account_usage(user["id"])
        if usage.get("workspaces", 0) >= cap:
            higher = [p for p in await list_plans(only_active=True)
                      if p.get("price", 0) > plan.get("price", 0)]
            suggestion = higher[0]["name"] if higher else None
            msg = (
                f"You hit your {plan.get('name') or plan['id']} plan's Workspaces limit ({cap}). "
                + (f"Upgrade to {suggestion} for more." if suggestion else "")
            )
            raise HTTPException(status_code=402, detail=msg)
    ws_id = str(uuid.uuid4())
    base_slug = slugify(f"{payload.name}-{ws_id[:6]}")
    doc = {
        "id": ws_id,
        "name": payload.name,
        "slug": base_slug,
        "type": payload.type,
        "owner_id": user["id"],
        "plan": "free",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.workspaces.insert_one(doc)
    doc.pop("_id", None)
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


class WorkspaceUpdateIn(BaseModel):
    name: str | None = None
    type: str | None = None  # "solo" | "agency"


@router.put("/workspaces/{workspace_id}")
async def update_workspace(workspace_id: str, payload: WorkspaceUpdateIn, request: Request):
    """Rename a workspace or change its type. Only the owner can do this."""
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user, ["owner"])
    db = get_db()
    ws = await db.workspaces.find_one({"id": workspace_id})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    update = {}
    if payload.name is not None:
        name = payload.name.strip()
        if not name or len(name) > 80:
            raise HTTPException(status_code=400, detail="Name must be 1-80 chars")
        update["name"] = name
    if payload.type is not None:
        if payload.type not in ("solo", "agency"):
            raise HTTPException(status_code=400, detail="Type must be solo or agency")
        update["type"] = payload.type
    if not update:
        return {**ws, "_id": None}
    await db.workspaces.update_one({"id": workspace_id}, {"$set": update})
    from services.audit import log as audit_log
    audit_log(action="workspace.update", actor=user, workspace_id=workspace_id,
              resource_type="workspace", resource_id=workspace_id,
              meta=update, request=request)
    fresh = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    return fresh


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str, request: Request, force: bool = False):
    """Permanently delete a workspace. Owner-only. Blocks if it's the user's
    last workspace, or if the workspace still holds apps/databases — unless
    `?force=true` is passed, in which case those resources are also wiped
    (and their Coolify counterparts deleted)."""
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user, ["owner"])
    db = get_db()
    ws = await db.workspaces.find_one({"id": workspace_id})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Don't let users lock themselves out
    owned_ids = await db.workspaces.distinct("id", {"owner_id": user["id"]})
    if len(owned_ids) <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete your last workspace — create another one first.")

    # Check for resources unless force=true
    apps_count = await db.apps.count_documents({"workspace_id": workspace_id})
    dbs_count = await db.databases.count_documents({"workspace_id": workspace_id})
    if (apps_count > 0 or dbs_count > 0) and not force:
        raise HTTPException(
            status_code=409,
            detail=f"Workspace still has {apps_count} app(s) and {dbs_count} database(s). Pass ?force=true to delete everything, or move/delete them first.",
        )

    # Hard cascade with build-engine cleanup when force=true.
    if force:
        from clients.coolify import coolify
        from services.subdomains import release_subdomain
        from services.github_webhooks import unregister_webhook as wh_unregister
        # Apps
        apps = await db.apps.find({"workspace_id": workspace_id}).to_list(500)
        for app in apps:
            if app.get("cloudflare_dns_record_id"):
                try: await release_subdomain(app)
                except Exception: pass
            if app.get("webhook_github_id"):
                try: await wh_unregister(app=app, workspace_id=workspace_id)
                except Exception: pass
            if app.get("coolify_app_uuid"):
                try: await coolify.delete_application(app["coolify_app_uuid"])
                except Exception: pass
        # Databases
        dbs = await db.databases.find({"workspace_id": workspace_id}).to_list(200)
        for d in dbs:
            if d.get("coolify_db_uuid"):
                try: await coolify.delete_database(d["coolify_db_uuid"])
                except Exception: pass
        # Drop everything
        await db.apps.delete_many({"workspace_id": workspace_id})
        await db.deployments.delete_many({"workspace_id": workspace_id})
        await db.domains.delete_many({"workspace_id": workspace_id})
        await db.databases.delete_many({"workspace_id": workspace_id})
        await db.cron_jobs.delete_many({"workspace_id": workspace_id})
        await db.pr_previews.delete_many({"workspace_id": workspace_id})

    # Workspace itself + membership + billing-side artefacts
    await db.workspaces.delete_one({"id": workspace_id})
    await db.workspace_members.delete_many({"workspace_id": workspace_id})
    await db.subscriptions.delete_many({"workspace_id": workspace_id})
    await db.billing_profiles.delete_many({"workspace_id": workspace_id})
    # Keep payments + invoices + audit_log as historical record.

    from services.audit import log as audit_log
    audit_log(action="workspace.delete", actor=user, workspace_id=workspace_id,
              resource_type="workspace", resource_id=workspace_id,
              meta={"name": ws.get("name"), "force": force,
                    "apps_deleted": apps_count, "databases_deleted": dbs_count},
              request=request)
    return {"deleted": True, "force": force, "apps_deleted": apps_count, "databases_deleted": dbs_count}


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
    # Note: members per Team are unconditionally unlimited on every plan.
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
    member.pop("_id", None)
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


@router.get("/workspaces/{workspace_id}/usage")
async def get_workspace_usage(workspace_id: str, request: Request):
    """Return current plan + usage counters + credit balance + any pending
    price change. One call powers the entire dashboard header."""
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    plan = await workspace_plan(workspace_id)
    usage = await workspace_usage(workspace_id)
    credits = await credits_balance(workspace_id)
    return {
        "plan": plan,
        "usage": usage,
        "credits": credits,
        "effective_price": await effective_price(workspace_id, plan),
        "price_change": await upcoming_change(workspace_id, plan),
        "billing_source": billing_source(user),
    }

