"""Cron jobs (scheduled tasks) per app.

Stored locally in db.cron_jobs and best-effort synced to Coolify so they
actually run inside the container. If Coolify is offline we still persist
the schedule and re-attempt on app redeploy / next save.

Schema (db.cron_jobs):
  id, app_id, workspace_id, name, command, schedule (cron expr),
  enabled, coolify_task_uuid (nullable), last_run_at, last_status,
  created_at, updated_at.
"""
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from clients.coolify import coolify
from services.audit import log as audit_log

router = APIRouter(tags=["cron"])
logger = logging.getLogger(__name__)

# Validate cron expressions (5 fields). Helpful pre-validation so we don't ship
# garbage to Coolify; this is the standard POSIX cron format.
_CRON_RE = re.compile(r"^\s*(\S+\s+){4}\S+\s*$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_cron(expr: str) -> None:
    if not _CRON_RE.match(expr or ""):
        raise HTTPException(status_code=400, detail="schedule must be a 5-field cron expression, e.g. '0 3 * * *'")


class CronIn(BaseModel):
    name: str
    command: str
    schedule: str  # cron expression
    enabled: bool = True


async def _resolve_app(app_id: str, user: dict, roles: Optional[list] = None) -> dict:
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, roles or ["owner", "admin", "developer"])
    return app


@router.get("/apps/{app_id}/cron")
async def list_cron(app_id: str, request: Request):
    user = await get_current_user(request)
    app = await _resolve_app(app_id, user, roles=None)
    jobs = await get_db().cron_jobs.find({"app_id": app_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"jobs": jobs, "app_id": app_id, "supports_build_engine_sync": bool(app.get("coolify_app_uuid"))}


@router.post("/apps/{app_id}/cron")
async def create_cron(app_id: str, payload: CronIn, request: Request):
    user = await get_current_user(request)
    app = await _resolve_app(app_id, user)
    _validate_cron(payload.schedule)
    db = get_db()
    job = {
        "id": str(uuid.uuid4()),
        "app_id": app_id,
        "workspace_id": app["workspace_id"],
        "name": payload.name.strip(),
        "command": payload.command,
        "schedule": payload.schedule.strip(),
        "enabled": bool(payload.enabled),
        "coolify_task_uuid": None,
        "last_run_at": None,
        "last_status": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    # Best-effort push to Coolify so it actually executes the cron.
    if app.get("coolify_app_uuid"):
        res = await coolify.create_scheduled_task(
            app["coolify_app_uuid"],
            name=job["name"], command=job["command"], frequency=job["schedule"],
        )
        if res and (res.get("uuid") or (res.get("data") or {}).get("uuid")):
            job["coolify_task_uuid"] = res.get("uuid") or res["data"]["uuid"]
    await db.cron_jobs.insert_one(dict(job))
    audit_log(
        action="cron.create", actor=user, workspace_id=app["workspace_id"],
        resource_type="cron_job", resource_id=job["id"],
        meta={"app_id": app_id, "name": job["name"], "schedule": job["schedule"]},
        request=request,
    )
    return job


@router.put("/apps/{app_id}/cron/{job_id}")
async def update_cron(app_id: str, job_id: str, payload: CronIn, request: Request):
    user = await get_current_user(request)
    app = await _resolve_app(app_id, user)
    _validate_cron(payload.schedule)
    db = get_db()
    job = await db.cron_jobs.find_one({"id": job_id, "app_id": app_id})
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found")
    update = {
        "name": payload.name.strip(),
        "command": payload.command,
        "schedule": payload.schedule.strip(),
        "enabled": bool(payload.enabled),
        "updated_at": _now_iso(),
    }
    # Sync to Coolify if we know about it.
    if app.get("coolify_app_uuid") and job.get("coolify_task_uuid"):
        await coolify.update_scheduled_task(
            app["coolify_app_uuid"], job["coolify_task_uuid"],
            name=update["name"], command=update["command"], frequency=update["schedule"],
        )
    elif app.get("coolify_app_uuid"):
        res = await coolify.create_scheduled_task(
            app["coolify_app_uuid"],
            name=update["name"], command=update["command"], frequency=update["schedule"],
        )
        if res and (res.get("uuid") or (res.get("data") or {}).get("uuid")):
            update["coolify_task_uuid"] = res.get("uuid") or res["data"]["uuid"]
    await db.cron_jobs.update_one({"id": job_id}, {"$set": update})
    audit_log(
        action="cron.update", actor=user, workspace_id=app["workspace_id"],
        resource_type="cron_job", resource_id=job_id,
        meta={"app_id": app_id, "name": update["name"]}, request=request,
    )
    out = await db.cron_jobs.find_one({"id": job_id}, {"_id": 0})
    return out


@router.delete("/apps/{app_id}/cron/{job_id}")
async def delete_cron(app_id: str, job_id: str, request: Request):
    user = await get_current_user(request)
    app = await _resolve_app(app_id, user)
    db = get_db()
    job = await db.cron_jobs.find_one({"id": job_id, "app_id": app_id})
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found")
    if app.get("coolify_app_uuid") and job.get("coolify_task_uuid"):
        await coolify.delete_scheduled_task(app["coolify_app_uuid"], job["coolify_task_uuid"])
    await db.cron_jobs.delete_one({"id": job_id})
    audit_log(
        action="cron.delete", actor=user, workspace_id=app["workspace_id"],
        resource_type="cron_job", resource_id=job_id,
        meta={"app_id": app_id, "name": job["name"]}, request=request,
    )
    return {"deleted": True}
