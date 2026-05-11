"""App management + Coolify deploy orchestration."""
import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from slugify import slugify

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from models import AppIn, EnvVarUpdate, AppUpdate, RedeployIn
from clients.coolify import coolify
from services.github_helpers import (
    detect_default_branch,
    inject_github_token,
    is_github_https,
    parse_repo,
    probe_repo_visibility,
    strip_token_from_url,
    workspace_github_token,
)
from services.deploy_keys import (
    add_github_deploy_key,
    generate_deploy_keypair,
    github_ssh_url,
    remove_github_deploy_key,
)
from services.log_parser import parse_log_lines, extract_failure_summary
from services.subdomains import provision_subdomain, release_subdomain
from services.github_webhooks import (
    generate_secret as wh_generate_secret,
    public_webhook_url as wh_public_url,
    register_webhook as wh_register,
    unregister_webhook as wh_unregister,
)
from services.plans import assert_limit

router = APIRouter(tags=["apps"])
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _append_log(deployment_id: str, line: str) -> None:
    """Best-effort append of a single log line to a deployment row."""
    db = get_db()
    try:
        await db.deployments.update_one(
            {"id": deployment_id}, {"$push": {"logs": line}}
        )
    except Exception as e:
        logger.warning("append_log failed for %s: %s", deployment_id, e)


async def _trigger_coolify_deploy_with_retry(
    app_id: str, deployment_id: str, coolify_uuid: str, max_attempts: int = 3
) -> str | None:
    """Call coolify.deploy() with exponential backoff. Returns the Coolify
    deployment_uuid on success, or None if every attempt fails. Logs each
    attempt to the DeployHub deployment row so the user sees what happened.
    """
    delay = 2.0
    last_error = "unknown"
    for attempt in range(1, max_attempts + 1):
        await _append_log(
            deployment_id,
            f"[BUILD] triggering coolify deploy — attempt {attempt}/{max_attempts}",
        )
        try:
            res = await coolify.deploy(coolify_uuid, force=True)
        except Exception as e:
            res = None
            last_error = str(e)[:200]
        if res and (res.get("deployment_uuid") or res.get("uuid")):
            cool_dep_uuid = res.get("deployment_uuid") or res.get("uuid")
            await _append_log(
                deployment_id,
                f"[BUILD] coolify deployment triggered (uuid={cool_dep_uuid})",
            )
            db = get_db()
            await db.deployments.update_one(
                {"id": deployment_id},
                {"$set": {"coolify_deployment_uuid": cool_dep_uuid}},
            )
            return cool_dep_uuid
        last_error = (res or {}).get("message") if isinstance(res, dict) else last_error
        await _append_log(
            deployment_id,
            f"[WARN] build engine returned no deploy id ({last_error or 'empty'}), retrying in {delay:.0f}s",
        )
        if attempt < max_attempts:
            await asyncio.sleep(delay)
            delay *= 2
    await _append_log(
        deployment_id,
        f"[ERROR] build engine failed to trigger deploy after {max_attempts} attempts — watchdog will reconcile",
    )
    return None


async def _redeploy_background(
    app_id: str, deployment_id: str, coolify_uuid: str, coolify_patch: dict | None = None
) -> None:
    """Background task for /redeploy: refresh the Coolify app's git_repository
    with a fresh GitHub token (so subscription / rotation works), apply any
    branch/commit patch, then call deploy with retries. Runs outside the HTTP
    request so the API returns in <100ms."""
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    patch = dict(coolify_patch or {})
    # Apps on the private-deploy-key flow don't need URL rewrites — the SSH
    # key is permanent and Coolify keeps `git_repository` as the SSH form.
    if app and is_github_https(app.get("repo_url") or "") and not app.get("coolify_private_key_uuid"):
        gh_token = await workspace_github_token(app["workspace_id"])
        if gh_token:
            # Best-effort shortcut: if the user has a token and the repo is
            # public, refreshing the clone URL doesn't hurt. For private repos
            # this won't work (Coolify strips the userinfo) — those should be
            # using _create_private_github_app at create time instead.
            visibility = await probe_repo_visibility(app["repo_url"])
            if visibility == "public":
                patch["git_repository"] = app["repo_url"]
            elif visibility == "private":
                await _append_log(
                    deployment_id,
                    "[WARN] this app was created before deploy-key support was "
                    "wired in. Delete and re-create the app to switch to the "
                    "deploy-key flow (recommended for private repos).",
                )
    if patch:
        await _append_log(deployment_id, f"[BUILD] applying build config patch: {', '.join(patch.keys())}")
        try:
            await coolify.update_application(coolify_uuid, patch)
        except Exception as e:
            await _append_log(deployment_id, f"[WARN] build config PATCH failed: {str(e)[:160]}")
    await _trigger_coolify_deploy_with_retry(app_id, deployment_id, coolify_uuid)


async def _create_private_github_app(
    app: dict,
    deployment_id: str | None,
    project_uuid: str,
    server_uuid: str,
) -> Optional[dict]:
    """Private-repo deploy path:
       1) Get the workspace's GitHub OAuth token (with `repo` scope).
       2) Generate an ed25519 SSH keypair.
       3) Upload the public key to the GitHub repo as a read-only deploy key.
       4) Register the private key in Coolify (is_git_related=true).
       5) Create a Coolify app via /applications/private-deploy-key with the
          SSH URL + private_key_uuid.
       6) Persist { github_deploy_key_id, coolify_private_key_uuid } on our app
          row so we can clean them up on delete.
    Returns the Coolify response (dict with `uuid`) on success, None on failure.
    """
    db = get_db()
    app_id = app["id"]
    parsed = parse_repo(app["repo_url"])
    if not parsed:
        if deployment_id:
            await _append_log(deployment_id, "[ERROR] could not parse GitHub repo URL")
        return None
    owner, repo_name = parsed

    gh_token = await workspace_github_token(app["workspace_id"])
    if not gh_token:
        if deployment_id:
            await _append_log(
                deployment_id,
                "[ERROR] this repo is private and no GitHub account is linked on this workspace. "
                "Open Settings → Connect GitHub (with repo scope), then redeploy.",
            )
        return None

    if deployment_id:
        await _append_log(deployment_id, f"[BUILD] private repo detected ({owner}/{repo_name}) — setting up deploy key")

    private_pem, public_key = generate_deploy_keypair()
    key_title = f"deployhub-{app['slug']}"
    gh_key_id = await add_github_deploy_key(owner, repo_name, key_title, public_key, gh_token)
    if not gh_key_id:
        if deployment_id:
            await _append_log(
                deployment_id,
                "[ERROR] could not add deploy key on GitHub — token likely missing 'repo' scope, "
                "or the repo is not accessible. Re-connect GitHub in Settings and retry.",
            )
        return None
    if deployment_id:
        await _append_log(deployment_id, f"[BUILD] deploy key uploaded to GitHub (id={gh_key_id}, read-only)")

    coolify_key = await coolify.create_private_key(
        name=f"deployhub-{app['slug']}-key",
        description=f"DeployHub auto-key for {owner}/{repo_name}",
        private_key=private_pem,
    )
    coolify_key_uuid = (coolify_key or {}).get("uuid")
    if not coolify_key_uuid:
        if deployment_id:
            await _append_log(deployment_id, "[ERROR] build engine rejected the private key — retry or check server logs")
        # Clean up the GitHub-side key so we don't leave dangling deploy keys
        await remove_github_deploy_key(owner, repo_name, gh_key_id, gh_token)
        return None
    if deployment_id:
        await _append_log(deployment_id, f"[BUILD] private key registered with build engine (uuid={coolify_key_uuid})")

    ssh_url = github_ssh_url(app["repo_url"]) or app["repo_url"]
    res = await coolify.create_private_deploy_key_app(
        project_uuid=project_uuid,
        server_uuid=server_uuid,
        name=app["slug"],
        git_repository=ssh_url,
        git_branch=app.get("branch") or "main",
        private_key_uuid=coolify_key_uuid,
        ports_exposes="3000",
        instant_deploy=False,
    )
    if res and res.get("uuid"):
        await db.apps.update_one(
            {"id": app_id},
            {"$set": {
                "coolify_private_key_uuid": coolify_key_uuid,
                "github_deploy_key_id": gh_key_id,
                "github_owner": owner,
                "github_repo": repo_name,
            }},
        )
        return res

    # Coolify refused the app → clean up both sides so a retry starts fresh.
    if deployment_id:
        await _append_log(deployment_id, "[WARN] build engine did not create the app — cleaning up deploy key")
    await remove_github_deploy_key(owner, repo_name, gh_key_id, gh_token)
    await coolify.delete_private_key(coolify_key_uuid)
    return None


async def _coolify_deploy(app_id: str, deployment_id: str | None = None):
    """Background task: create Coolify project+app and deploy.

    Uses a 2-step flow — first create the app with instant_deploy=False, then
    explicitly call /deploy with retries. This avoids the silent-failure mode
    of instant_deploy=True when the Coolify queue is busy or the network
    hiccups (Coolify returns 200 but never actually queues the deployment).
    """
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        return

    # Resolve which deployment row we're tracking.
    if deployment_id is None:
        doc = await db.deployments.find_one(
            {"app_id": app_id, "status": "queued"},
            {"_id": 0, "id": 1},
            sort=[("started_at", -1)],
        )
        deployment_id = doc["id"] if doc else None

    async def _fail_deploy(msg: str):
        await db.apps.update_one({"id": app_id}, {"$set": {"status": "failed"}})
        if deployment_id:
            await _append_log(deployment_id, f"[ERROR] {msg}")
            await db.deployments.update_one(
                {"id": deployment_id},
                {"$set": {"status": "failed", "finished_at": _now_iso()}},
            )

    if not coolify.configured:
        # Mark as deployed-stub so the UX doesn't get stuck.
        await db.apps.update_one(
            {"id": app_id},
            {"$set": {"status": "live", "primary_url": f"https://{app['slug']}.deploy.example", "last_deploy_at": _now_iso()}},
        )
        await db.deployments.update_one(
            {"app_id": app_id, "status": "queued"},
            {"$set": {"status": "live", "finished_at": _now_iso(),
                      "logs": ["[BUILD] build engine not configured — using stub deployment", "[STATUS] live"]}},
        )
        return

    server_uuid = await coolify.get_default_server_uuid()
    if not server_uuid:
        await _fail_deploy("no build server available")
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
        await _fail_deploy("could not create build project")
        return

    await db.apps.update_one({"id": app_id}, {"$set": {"status": "building"}})
    if deployment_id:
        await db.deployments.update_one(
            {"id": deployment_id},
            {"$set": {"status": "building"}},
        )
        await _append_log(deployment_id, "[BUILD] project ready")
        await _append_log(deployment_id, "[BUILD] creating application...")

    # -------------------------------------------------------------------
    # Decide: public repo → /applications/public
    #         private GitHub repo → generate deploy key, upload to GitHub,
    #                                register in Coolify, use /applications/private-deploy-key
    # -------------------------------------------------------------------
    res = None
    used_private_flow = False
    if is_github_https(app["repo_url"]):
        visibility = await probe_repo_visibility(app["repo_url"])
        if visibility == "private":
            used_private_flow = True
            res = await _create_private_github_app(app, deployment_id, project_uuid, server_uuid)
    if not used_private_flow:
        res = await coolify.create_public_app(
            project_uuid=project_uuid,
            server_uuid=server_uuid,
            name=app["slug"],
            git_repository=app["repo_url"],
            git_branch=app.get("branch") or "main",
            ports_exposes="3000",
            instant_deploy=False,
        )
    if not res or not res.get("uuid"):
        await _fail_deploy("build engine create app failed — check repo URL and try again")
        return

    coolify_uuid = res["uuid"]
    await db.apps.update_one({"id": app_id}, {"$set": {"coolify_app_uuid": coolify_uuid}})
    if deployment_id:
        await _append_log(deployment_id, f"[BUILD] application created (uuid={coolify_uuid})")

    # Tell Coolify about the auto-provisioned subdomain so Traefik issues SSL.
    if app.get("cloudflare_fqdn"):
        try:
            await coolify.update_application(
                coolify_uuid, {"fqdn": f"https://{app['cloudflare_fqdn']}"}
            )
            if deployment_id:
                await _append_log(
                    deployment_id, f"[BUILD] domain assigned: {app['cloudflare_fqdn']}"
                )
        except Exception as e:
            logger.warning("coolify fqdn sync for auto-subdomain failed: %s", e)

    if app.get("env_vars"):
        await coolify.update_env(coolify_uuid, app["env_vars"])
        if deployment_id:
            await _append_log(deployment_id, f"[BUILD] pushed {len(app['env_vars'])} env vars to build engine")

    # Step 2 — explicitly trigger the deploy with retries.
    if deployment_id:
        cool_dep_uuid = await _trigger_coolify_deploy_with_retry(
            app_id, deployment_id, coolify_uuid
        )
        if not cool_dep_uuid:
            await _fail_deploy(
                "coolify /deploy returned no deployment uuid after 3 retries. "
                "The monitor watchdog will retry if a Coolify deployment becomes visible."
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
    # Enforce the workspace's plan limit before we do any work.
    await assert_limit(payload.workspace_id, "apps")
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

    # Auto-provision a free {slug}.zone subdomain if Cloudflare is configured.
    # Falls back silently if not — app still gets created with a Coolify URL.
    sub = await provision_subdomain(doc)
    if sub:
        doc["primary_url"] = sub["primary_url"]
        doc["cloudflare_dns_record_id"] = sub["record_id"]
        doc["cloudflare_fqdn"] = sub["fqdn"]

    # Generate a webhook secret upfront so the registration + UI work in
    # one round-trip. If we can't talk to GitHub yet, the secret stays
    # local and the user can paste the URL manually.
    doc["webhook_secret"] = wh_generate_secret()
    doc["webhook_url"] = wh_public_url(app_id)
    doc["webhook_enabled"] = True

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
    background.add_task(_coolify_deploy, app_id, deploy_doc["id"])
    # Best-effort GitHub webhook auto-registration. Fires in the background so
    # we don't slow down /apps response. The function itself is no-op-safe.
    background.add_task(_auto_register_webhook, app_id)
    return doc


async def _auto_register_webhook(app_id: str) -> None:
    """Background task: try to register a GitHub webhook for this app. Stores
    `webhook_github_id` on success so we can unregister it later."""
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        return
    res = await wh_register(app=app, workspace_id=app["workspace_id"])
    if not res:
        return
    await db.apps.update_one(
        {"id": app_id},
        {"$set": {"webhook_github_id": res["id"], "webhook_secret": res["secret"]}},
    )


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

    # Release any auto-provisioned Cloudflare subdomain.
    if app.get("cloudflare_dns_record_id"):
        try:
            await release_subdomain(app)
        except Exception as e:
            logger.warning("cloudflare release_subdomain failed: %s", e)

    # Unregister the GitHub webhook so we don't leave a dead endpoint on the
    # customer's repo.
    if app.get("webhook_github_id"):
        try:
            await wh_unregister(app=app, workspace_id=app["workspace_id"])
        except Exception as e:
            logger.warning("github webhook unregister failed: %s", e)

    # Clean up deploy key artefacts so we don't leave dead keys on GitHub or Coolify.
    if app.get("coolify_app_uuid"):
        try:
            await coolify.delete_application(app["coolify_app_uuid"])
        except Exception as e:
            logger.warning("coolify delete_application failed: %s", e)
    if app.get("coolify_private_key_uuid"):
        try:
            await coolify.delete_private_key(app["coolify_private_key_uuid"])
        except Exception as e:
            logger.warning("coolify delete_private_key failed: %s", e)
    if app.get("github_deploy_key_id") and app.get("github_owner") and app.get("github_repo"):
        gh_token = await workspace_github_token(app["workspace_id"])
        if gh_token:
            await remove_github_deploy_key(
                app["github_owner"], app["github_repo"], app["github_deploy_key_id"], gh_token
            )

    await db.apps.delete_one({"id": app_id})
    await db.deployments.delete_many({"app_id": app_id})
    await db.domains.delete_many({"app_id": app_id})
    await db.monitoring_results.delete_many({"app_id": app_id})
    return {"deleted": True}


@router.patch("/apps/{app_id}")
async def update_app(app_id: str, payload: AppUpdate, request: Request, background: BackgroundTasks):
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

    # Sync to Coolify if connected — fire-and-forget so the HTTP response
    # is fast. Coolify PATCH can occasionally take >10s when the instance
    # is under load.
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
            background.add_task(coolify.update_application, app["coolify_app_uuid"], coolify_payload)

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
        # Build Coolify patch (branch/commit) and hand off to background task.
        # The background task applies the patch, then retries coolify /deploy
        # with exponential backoff. Keeps the HTTP response fast.
        coolify_patch = {}
        if payload.branch:
            coolify_patch["git_branch"] = target_branch
        if target_commit:
            coolify_patch["git_commit_sha"] = target_commit
        await db.apps.update_one({"id": app_id}, {"$set": {"status": "building"}})
        await db.deployments.update_one(
            {"id": deploy_doc["id"]},
            {"$set": {"status": "building"}},
        )
        background.add_task(
            _redeploy_background,
            app_id,
            deploy_doc["id"],
            app["coolify_app_uuid"],
            coolify_patch or None,
        )
    else:
        background.add_task(_coolify_deploy, app_id, deploy_doc["id"])

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
async def update_env(app_id: str, payload: EnvVarUpdate, request: Request, background: BackgroundTasks):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])
    await db.apps.update_one({"id": app_id}, {"$set": {"env_vars": payload.env_vars}})
    if coolify.configured and app.get("coolify_app_uuid"):
        background.add_task(coolify.update_env, app["coolify_app_uuid"], payload.env_vars)
    return {"env_vars": payload.env_vars}



# ─────────────────────── GitHub Webhook controls ───────────────────────
@router.get("/apps/{app_id}/webhook")
async def get_webhook(app_id: str, request: Request):
    """Returns the webhook URL + secret + GitHub registration status for the
    AppDetail UI to display."""
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    return {
        "url": app.get("webhook_url") or wh_public_url(app_id),
        "secret": app.get("webhook_secret"),
        "enabled": bool(app.get("webhook_enabled", True)),
        "github_hook_id": app.get("webhook_github_id"),
        "auto_registered": bool(app.get("webhook_github_id")),
        "branch": app.get("branch") or "main",
    }


@router.post("/apps/{app_id}/webhook/toggle")
async def toggle_webhook(app_id: str, request: Request):
    """Enable/disable auto-deploy on push (flips webhook_enabled)."""
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])
    new_val = not bool(app.get("webhook_enabled", True))
    await db.apps.update_one({"id": app_id}, {"$set": {"webhook_enabled": new_val}})
    return {"enabled": new_val}


@router.post("/apps/{app_id}/webhook/rotate")
async def rotate_webhook(app_id: str, request: Request, background: BackgroundTasks):
    """Generate a new secret + re-register with GitHub. Used when the user
    suspects the secret leaked."""
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])
    new_secret = wh_generate_secret()
    await db.apps.update_one({"id": app_id}, {"$set": {"webhook_secret": new_secret}})
    background.add_task(_auto_register_webhook, app_id)
    return {"secret": new_secret, "url": app.get("webhook_url") or wh_public_url(app_id)}


@router.post("/apps/{app_id}/webhook/register")
async def manual_register_webhook(app_id: str, request: Request):
    """Trigger a fresh GitHub webhook registration (e.g. after connecting GH
    OAuth post-creation). Returns 200 even if registration is skipped."""
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])
    res = await wh_register(app=app, workspace_id=app["workspace_id"])
    if res:
        await db.apps.update_one(
            {"id": app_id},
            {"$set": {"webhook_github_id": res["id"], "webhook_secret": res["secret"]}},
        )
        return {"registered": True, "hook_id": res["id"]}
    return {"registered": False, "reason": "no GitHub token, or repo not accessible"}
