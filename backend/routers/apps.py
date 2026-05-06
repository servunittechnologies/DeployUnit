"""App management + Coolify deploy orchestration."""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from slugify import slugify

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from models import AppIn, EnvVarUpdate, AppUpdate, RedeployIn
from clients.coolify import coolify
from services.github_helpers import detect_default_branch
from services.log_parser import parse_log_lines, extract_failure_summary

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

    # Branch auto-detection: if caller passed nothing or "main", verify it actually exists.
    requested_branch = (payload.branch or "main").strip()
    branch_to_use = requested_branch
    auto_detected = await detect_default_branch(repo, user_id=user["id"])
    if auto_detected and (not payload.branch or payload.branch.lower() == "main") and auto_detected != requested_branch:
        branch_to_use = auto_detected
        logger.info("branch auto-detected %s -> %s for %s", requested_branch, branch_to_use, repo)

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
        "branch": branch_to_use,
        "build_command": payload.build_command,
        "start_command": payload.start_command,
        "env_vars": payload.env_vars or {},
        "coolify_app_uuid": None,
        "status": "queued",
        "primary_url": None,
        "tier": "development",
        "protected_branches": ["main"],
        "auto_deploy": True,
        "last_deploy_at": _now_iso(),
        "created_at": _now_iso(),
    }
    await db.apps.insert_one(doc)
    doc.pop("_id", None)

    initial_logs = ["[QUEUE] deployment queued"]
    if branch_to_use != requested_branch:
        initial_logs.append(f"[QUEUE] branch auto-detected: requested '{requested_branch}', using '{branch_to_use}' (default on GitHub)")

    deploy_doc = {
        "id": str(uuid.uuid4()),
        "app_id": app_id,
        "workspace_id": payload.workspace_id,
        "status": "queued",
        "commit_sha": None,
        "commit_message": "Initial deployment",
        "branch": branch_to_use,
        "logs": initial_logs,
        "started_at": _now_iso(),
        "finished_at": None,
    }
    await db.deployments.insert_one(deploy_doc)
    deploy_doc.pop("_id", None)
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


@router.patch("/apps/{app_id}")
async def update_app(app_id: str, payload: AppUpdate, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])

    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None or k in {"build_command", "start_command", "project_id"}}
    if not update:
        return await db.apps.find_one({"id": app_id}, {"_id": 0})

    if "name" in update:
        update["slug"] = slugify(f"{update['name']}-{app_id[:6]}")

    await db.apps.update_one({"id": app_id}, {"$set": update})

    # Sync to Coolify if connected
    if coolify.configured and app.get("coolify_app_uuid"):
        coolify_payload = {}
        if "branch" in update and update["branch"]:
            coolify_payload["git_branch"] = update["branch"]
        if "build_command" in update:
            coolify_payload["build_command"] = update["build_command"] or ""
        if "start_command" in update:
            coolify_payload["custom_start_command"] = update["start_command"] or ""
        if "name" in update:
            coolify_payload["name"] = update["slug"]
        if coolify_payload:
            await coolify.update_application(app["coolify_app_uuid"], coolify_payload)

    return await db.apps.find_one({"id": app_id}, {"_id": 0})


@router.post("/apps/{app_id}/redeploy")
async def redeploy(app_id: str, request: Request, background: BackgroundTasks, payload: RedeployIn | None = None):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])

    payload = payload or RedeployIn()
    target_branch = (payload.branch or app.get("branch") or "main").strip()
    target_commit = (payload.commit_sha or "").strip() or None

    # Branch protection — production-tier apps may only deploy from listed branches
    if app.get("tier") == "production":
        allowed = app.get("protected_branches") or ["main"]
        if target_branch not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Branch protection: '{target_branch}' is not allowed for this production-tier app. Allowed: {', '.join(allowed)}",
            )

    msg = payload.commit_message or "Manual redeploy"
    if target_commit:
        msg = f"{msg} ({target_branch}@{target_commit[:7]})"
    elif payload.branch and payload.branch != app.get("branch"):
        msg = f"{msg} (switch to {target_branch})"

    deploy_doc = {
        "id": str(uuid.uuid4()),
        "app_id": app_id,
        "workspace_id": app["workspace_id"],
        "status": "queued",
        "commit_sha": target_commit,
        "commit_message": msg,
        "branch": target_branch,
        "logs": [
            "[QUEUE] redeploy queued",
            f"[QUEUE] branch={target_branch}" + (f" commit={target_commit[:7]}" if target_commit else ""),
        ],
        "started_at": _now_iso(),
        "finished_at": None,
    }
    await db.deployments.insert_one(deploy_doc)
    deploy_doc.pop("_id", None)

    app_update = {"status": "queued", "last_deploy_at": _now_iso()}
    if payload.branch:
        app_update["branch"] = target_branch
    await db.apps.update_one({"id": app_id}, {"$set": app_update})

    if coolify.configured and app.get("coolify_app_uuid"):
        # If switching branch / commit, update Coolify app first
        coolify_patch = {}
        if payload.branch:
            coolify_patch["git_branch"] = target_branch
        if target_commit:
            coolify_patch["git_commit_sha"] = target_commit
        if coolify_patch:
            await coolify.update_application(app["coolify_app_uuid"], coolify_patch)
        await coolify.deploy(app["coolify_app_uuid"], force=True)
        await db.apps.update_one({"id": app_id}, {"$set": {"status": "building"}})
        await db.deployments.update_one(
            {"id": deploy_doc["id"]},
            {"$set": {
                "status": "building",
                "logs": (deploy_doc.get("logs") or []) + ["[BUILD] redeploy triggered on coolify"],
            }},
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


@router.post("/apps/{app_id}/rollback/{deployment_id}")
async def rollback(app_id: str, deployment_id: str, request: Request, background: BackgroundTasks):
    """Pin a past deployment as live by re-running it (its branch + commit)."""
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])

    target = await db.deployments.find_one({"id": deployment_id, "app_id": app_id})
    if not target:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if target.get("status") in ("queued", "building"):
        raise HTTPException(status_code=400, detail="That deployment is still in progress.")

    branch = target.get("branch") or app.get("branch") or "main"
    commit_sha = target.get("commit_sha")

    if app.get("tier") == "production":
        allowed = app.get("protected_branches") or ["main"]
        if branch not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Branch protection: '{branch}' is not allowed for this production-tier app.",
            )

    redeploy_payload = RedeployIn(
        branch=branch,
        commit_sha=commit_sha,
        commit_message=f"Rollback to {target.get('commit_sha', '?')[:7] if target.get('commit_sha') else 'previous deploy'}",
    )
    return await redeploy(app_id, request, background, redeploy_payload)


@router.get("/apps/{app_id}/health")
async def app_health(app_id: str, request: Request):
    """Single live health probe for the Overview preview card."""
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    url = app.get("primary_url")
    if not url:
        return {"available": False, "reason": "no_url"}
    import time
    import httpx as _httpx
    start = time.perf_counter()
    try:
        async with _httpx.AsyncClient(timeout=8.0, follow_redirects=True) as cli:
            r = await cli.get(url, headers={"User-Agent": "DeployHub-Health/1.0"})
        elapsed = int((time.perf_counter() - start) * 1000)
        title = None
        if r.headers.get("content-type", "").lower().startswith("text/html"):
            import re as _re
            m = _re.search(r"<title[^>]*>([^<]{1,200})</title>", r.text, _re.I)
            if m:
                title = m.group(1).strip()
        # Detect framing — sites that disallow iframe via X-Frame-Options or CSP
        xfo = (r.headers.get("x-frame-options") or "").lower()
        csp = r.headers.get("content-security-policy") or ""
        framing_blocked = xfo in ("deny", "sameorigin") or "frame-ancestors" in csp
        return {
            "available": True,
            "url": url,
            "status_code": r.status_code,
            "ok": 200 <= r.status_code < 400,
            "response_time_ms": elapsed,
            "title": title,
            "framing_blocked": framing_blocked,
            "checked_at": _now_iso(),
        }
    except Exception as e:
        return {
            "available": False,
            "url": url,
            "reason": str(e)[:200],
            "ok": False,
            "checked_at": _now_iso(),
        }


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
