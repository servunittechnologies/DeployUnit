"""PR Preview Deploys — Vercel-style ephemeral apps per pull request.

For every opened/synchronize/reopened pull_request event on the app's repo
we spin up a child "preview" app on Coolify with the PR's branch checked
out. On closed/merged we tear it down.

Schema (db.pr_previews):
  id, parent_app_id, workspace_id, pr_number, branch, status,
  preview_app_id (FK to db.apps for the ephemeral child), commit_sha,
  primary_url, created_at, closed_at.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi.responses import JSONResponse

from db import get_db
from services.subdomains import provision_subdomain, release_subdomain
from clients.coolify import coolify

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def handle_pr_event(*, parent_app: dict, payload: dict, background) -> JSONResponse:
    """Entrypoint called by routers/webhooks.py for X-GitHub-Event: pull_request."""
    action = (payload or {}).get("action") or ""
    pr = (payload or {}).get("pull_request") or {}
    number = pr.get("number")
    branch = (pr.get("head") or {}).get("ref")
    sha = (pr.get("head") or {}).get("sha")
    if not number or not branch:
        return JSONResponse(status_code=200, content={"status": "ignored", "reason": "missing pr/number/branch"})

    db = get_db()

    # OPENED / SYNCHRONIZE / REOPENED → create or update the preview
    if action in ("opened", "synchronize", "reopened"):
        return await _create_or_update_preview(
            parent_app=parent_app, number=number, branch=branch, sha=sha, background=background
        )

    # CLOSED → tear down (covers merged-and-closed too because GitHub fires close)
    if action == "closed":
        existing = await db.pr_previews.find_one({"parent_app_id": parent_app["id"], "pr_number": number})
        if not existing:
            return JSONResponse(status_code=200, content={"status": "noop", "reason": "no preview existed"})
        background.add_task(_teardown_preview, existing)
        return JSONResponse(
            status_code=202, content={"status": "teardown_queued", "pr_number": number},
        )

    return JSONResponse(status_code=200, content={"status": "ignored", "reason": f"action={action}"})


async def _create_or_update_preview(*, parent_app: dict, number: int, branch: str, sha: Optional[str], background) -> JSONResponse:
    """Idempotent: existing preview → trigger a redeploy on the PR branch;
    new preview → create a child app + first deploy."""
    db = get_db()
    existing = await db.pr_previews.find_one({"parent_app_id": parent_app["id"], "pr_number": number})

    if existing:
        # Re-deploy: update branch (PR may have re-pushed) and queue a build.
        await db.pr_previews.update_one(
            {"id": existing["id"]},
            {"$set": {"branch": branch, "commit_sha": sha, "status": "building", "updated_at": _now_iso()}},
        )
        # Reuse the existing child app — trigger a redeploy.
        from routers.apps import _redeploy_background
        deploy_id = str(uuid.uuid4())
        preview_app = await db.apps.find_one({"id": existing["preview_app_id"]})
        if not preview_app:
            return JSONResponse(status_code=410, content={"status": "stale", "reason": "child app missing"})
        # Update child app branch on disk + trigger redeploy.
        await db.apps.update_one({"id": preview_app["id"]}, {"$set": {"branch": branch}})
        await db.deployments.insert_one({
            "id": deploy_id, "app_id": preview_app["id"], "workspace_id": preview_app["workspace_id"],
            "status": "queued", "branch": branch, "commit_sha": sha,
            "commit_message": f"PR #{number} update",
            "trigger": "pr_preview",
            "logs": [f"[QUEUE] PR #{number} preview sync"],
            "started_at": _now_iso(), "finished_at": None,
        })
        cool_uuid = preview_app.get("coolify_app_uuid")
        if cool_uuid:
            background.add_task(_redeploy_background, preview_app["id"], deploy_id, cool_uuid, None)
        else:
            from routers.apps import _coolify_deploy
            background.add_task(_coolify_deploy, preview_app["id"], deploy_id)
        return JSONResponse(status_code=202, content={"status": "redeploy_queued", "pr_number": number, "preview_app_id": preview_app["id"]})

    # ─── New PR preview: create a child app ───
    preview_id = str(uuid.uuid4())
    deploy_id = str(uuid.uuid4())
    base_slug = f"{parent_app.get('slug') or parent_app['id'][:8]}-pr-{number}"

    child_app = {
        "id": preview_id,
        "workspace_id": parent_app["workspace_id"],
        "project_id": parent_app.get("project_id"),
        "name": f"{parent_app['name']} · PR #{number}",
        "slug": base_slug,
        "framework": parent_app.get("framework"),
        "repo_url": parent_app["repo_url"],
        "branch": branch,
        "build_command": parent_app.get("build_command"),
        "start_command": parent_app.get("start_command"),
        "env_vars": dict(parent_app.get("env_vars") or {}),
        "coolify_app_uuid": None,
        "status": "queued",
        "primary_url": None,
        "tier": "preview",
        "auto_deploy": True,
        "last_deploy_at": _now_iso(),
        "created_at": _now_iso(),
        "is_pr_preview": True,
        "pr_number": number,
        "parent_app_id": parent_app["id"],
    }
    # Auto-subdomain (uses {slug}.{zone_name} → unique because slug has -pr-{number})
    sub = await provision_subdomain(child_app)
    if sub:
        child_app["primary_url"] = sub["primary_url"]
        child_app["cloudflare_dns_record_id"] = sub["record_id"]
        child_app["cloudflare_fqdn"] = sub["fqdn"]

    await db.apps.insert_one(dict(child_app))

    await db.pr_previews.insert_one({
        "id": str(uuid.uuid4()),
        "parent_app_id": parent_app["id"],
        "workspace_id": parent_app["workspace_id"],
        "pr_number": number,
        "branch": branch,
        "commit_sha": sha,
        "status": "building",
        "preview_app_id": preview_id,
        "primary_url": child_app.get("primary_url"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "closed_at": None,
    })

    await db.deployments.insert_one({
        "id": deploy_id, "app_id": preview_id, "workspace_id": parent_app["workspace_id"],
        "status": "queued", "branch": branch, "commit_sha": sha,
        "commit_message": f"PR #{number} preview",
        "trigger": "pr_preview",
        "logs": [f"[QUEUE] PR #{number} preview · branch={branch}"],
        "started_at": _now_iso(), "finished_at": None,
    })

    from routers.apps import _coolify_deploy
    background.add_task(_coolify_deploy, preview_id, deploy_id)

    return JSONResponse(
        status_code=202,
        content={
            "status": "preview_queued",
            "pr_number": number,
            "preview_app_id": preview_id,
            "primary_url": child_app.get("primary_url"),
        },
    )


async def _teardown_preview(preview: dict) -> None:
    """Delete the child app + Coolify resources + DNS record. Idempotent."""
    db = get_db()
    preview_app_id = preview.get("preview_app_id")
    if not preview_app_id:
        return
    child = await db.apps.find_one({"id": preview_app_id})
    if child:
        # Reuse the proper teardown path from routers.apps.delete_app — we
        # can't call the FastAPI handler directly (it needs Request), so
        # inline the resource cleanup steps.
        if child.get("cloudflare_dns_record_id"):
            try:
                await release_subdomain(child)
            except Exception as e:
                logger.warning("pr_preview release_subdomain failed: %s", e)
        if child.get("coolify_app_uuid"):
            try:
                await coolify.delete_application(child["coolify_app_uuid"])
            except Exception as e:
                logger.warning("pr_preview delete_application failed: %s", e)
        await db.apps.delete_one({"id": preview_app_id})
        await db.deployments.delete_many({"app_id": preview_app_id})
    await db.pr_previews.update_one(
        {"id": preview["id"]},
        {"$set": {"status": "closed", "closed_at": _now_iso()}},
    )
