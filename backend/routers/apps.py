"""App management + Coolify deploy orchestration."""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from slugify import slugify

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from models import AppIn, EnvVarUpdate
from clients.coolify import coolify

router = APIRouter(tags=["apps"])
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _coolify_deploy(app_id: str):
    """Background task: create Coolify project+app and deploy."""
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        return
    if not coolify.configured:
        # Mark as deployed-stub so the UX doesn't get stuck.
        await db.apps.update_one(
            {"id": app_id},
            {"$set": {"status": "live", "primary_url": f"https://{app['slug']}.deploy.example", "last_deploy_at": _now_iso()}},
        )
        await db.deployments.update_one(
            {"app_id": app_id, "status": "queued"},
            {"$set": {"status": "live", "finished_at": _now_iso(),
                      "logs": ["[BUILD] coolify_not_configured — using stub deployment", "[STATUS] live"]}},
        )
        return

    server_uuid = await coolify.get_default_server_uuid()
    if not server_uuid:
        await db.apps.update_one({"id": app_id}, {"$set": {"status": "failed"}})
        await db.deployments.update_one(
            {"app_id": app_id, "status": "queued"},
            {"$set": {"status": "failed", "finished_at": _now_iso(),
                      "logs": ["[ERROR] no coolify server available"]}},
        )
        return

    # Create or reuse a coolify project per workspace
    project_uuid = None
    ws = await db.workspaces.find_one({"id": app["workspace_id"]})
    if ws and ws.get("coolify_project_uuid"):
        project_uuid = ws["coolify_project_uuid"]
    else:
        proj = await coolify.create_project(name=ws["name"] if ws else f"deployhub-{app['workspace_id'][:6]}")
        if proj and proj.get("uuid"):
            project_uuid = proj["uuid"]
            await db.workspaces.update_one({"id": app["workspace_id"]}, {"$set": {"coolify_project_uuid": project_uuid}})

    if not project_uuid:
        await db.apps.update_one({"id": app_id}, {"$set": {"status": "failed"}})
        await db.deployments.update_one(
            {"app_id": app_id, "status": "queued"},
            {"$set": {"status": "failed", "finished_at": _now_iso(),
                      "logs": ["[ERROR] could not create coolify project"]}},
        )
        return

    await db.apps.update_one({"id": app_id}, {"$set": {"status": "building"}})
    await db.deployments.update_one(
        {"app_id": app_id, "status": "queued"},
        {"$set": {"status": "building", "logs": ["[BUILD] coolify project ready", "[BUILD] creating application..."]}},
    )

    res = await coolify.create_public_app(
        project_uuid=project_uuid,
        server_uuid=server_uuid,
        name=app["slug"],
        git_repository=app["repo_url"],
        git_branch=app.get("branch") or "main",
        ports_exposes="3000",
        instant_deploy=True,
    )
    if not res or not res.get("uuid"):
        await db.apps.update_one({"id": app_id}, {"$set": {"status": "failed"}})
        await db.deployments.update_one(
            {"app_id": app_id, "status": "building"},
            {"$set": {"status": "failed", "finished_at": _now_iso(),
                      "logs": ["[ERROR] coolify create app failed"]}},
        )
        return

    coolify_uuid = res["uuid"]
    await db.apps.update_one({"id": app_id}, {"$set": {"coolify_app_uuid": coolify_uuid}})
    if app.get("env_vars"):
        await coolify.update_env(coolify_uuid, app["env_vars"])
    await db.deployments.update_one(
        {"app_id": app_id, "status": "building"},
        {"$set": {"logs": ["[BUILD] coolify created app", "[BUILD] deploy triggered"]}},
    )


def _validate_repo_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="repo_url is required")
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("git@")):
        raise HTTPException(status_code=400, detail="repo_url must be http(s) or git@ URL")
    return url


@router.get("/apps")
async def list_apps(workspace_id: str, request: Request, project_id: str | None = None):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    q = {"workspace_id": workspace_id}
    if project_id:
        q["project_id"] = project_id
    return await db.apps.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


@router.post("/apps")
async def create_app(payload: AppIn, request: Request, background: BackgroundTasks):
    user = await get_current_user(request)
    await require_workspace_member(payload.workspace_id, user, ["owner", "admin", "developer"])
    db = get_db()
    repo = _validate_repo_url(payload.repo_url)
    app_id = str(uuid.uuid4())
    base_slug = slugify(f"{payload.name}-{app_id[:6]}")
    doc = {
        "id": app_id,
        "workspace_id": payload.workspace_id,
        "project_id": payload.project_id,
        "name": payload.name,
        "slug": base_slug,
        "framework": payload.framework,
        "repo_url": repo,
        "branch": payload.branch or "main",
        "build_command": payload.build_command,
        "start_command": payload.start_command,
        "env_vars": payload.env_vars or {},
        "coolify_app_uuid": None,
        "status": "queued",
        "primary_url": None,
        "last_deploy_at": _now_iso(),
        "created_at": _now_iso(),
    }
    await db.apps.insert_one(doc)
    deploy_doc = {
        "id": str(uuid.uuid4()),
        "app_id": app_id,
        "workspace_id": payload.workspace_id,
        "status": "queued",
        "commit_sha": None,
        "commit_message": "Initial deployment",
        "branch": doc["branch"],
        "logs": ["[QUEUE] deployment queued"],
        "started_at": _now_iso(),
        "finished_at": None,
    }
    await db.deployments.insert_one(deploy_doc)
    background.add_task(_coolify_deploy, app_id)
    return doc


@router.get("/apps/{app_id}")
async def get_app(app_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    return app


@router.delete("/apps/{app_id}")
async def delete_app(app_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])
    await db.apps.delete_one({"id": app_id})
    await db.deployments.delete_many({"app_id": app_id})
    await db.domains.delete_many({"app_id": app_id})
    await db.monitoring_results.delete_many({"app_id": app_id})
    return {"deleted": True}


@router.post("/apps/{app_id}/redeploy")
async def redeploy(app_id: str, request: Request, background: BackgroundTasks):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])

    deploy_doc = {
        "id": str(uuid.uuid4()),
        "app_id": app_id,
        "workspace_id": app["workspace_id"],
        "status": "queued",
        "commit_sha": None,
        "commit_message": "Manual redeploy",
        "branch": app.get("branch") or "main",
        "logs": ["[QUEUE] redeploy queued"],
        "started_at": _now_iso(),
        "finished_at": None,
    }
    await db.deployments.insert_one(deploy_doc)
    await db.apps.update_one({"id": app_id}, {"$set": {"status": "queued", "last_deploy_at": _now_iso()}})

    if coolify.configured and app.get("coolify_app_uuid"):
        await coolify.deploy(app["coolify_app_uuid"], force=True)
        await db.apps.update_one({"id": app_id}, {"$set": {"status": "building"}})
        await db.deployments.update_one(
            {"id": deploy_doc["id"]},
            {"$set": {"status": "building", "logs": ["[BUILD] redeploy triggered on coolify"]}},
        )
    else:
        background.add_task(_coolify_deploy, app_id)

    return {**deploy_doc, "status": "building" if coolify.configured else "queued"}


@router.post("/apps/{app_id}/restart")
async def restart_app(app_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])
    if coolify.configured and app.get("coolify_app_uuid"):
        await coolify.restart(app["coolify_app_uuid"])
    return {"ok": True}


@router.get("/apps/{app_id}/env")
async def get_env(app_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    return {"env_vars": app.get("env_vars", {})}


@router.put("/apps/{app_id}/env")
async def update_env(app_id: str, payload: EnvVarUpdate, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])
    await db.apps.update_one({"id": app_id}, {"$set": {"env_vars": payload.env_vars}})
    if coolify.configured and app.get("coolify_app_uuid"):
        await coolify.update_env(app["coolify_app_uuid"], payload.env_vars)
    return {"env_vars": payload.env_vars}
