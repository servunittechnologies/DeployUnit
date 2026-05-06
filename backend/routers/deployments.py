"""Deployment routes — list, detail, parsed logs, and SSE live stream."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from clients.coolify import coolify
from services.log_parser import parse_log_lines, extract_failure_summary

logger = logging.getLogger(__name__)
router = APIRouter(tags=["deployments"])


def _parse_coolify_logs(raw) -> list[str]:
    """Coolify stores logs as a JSON-encoded array of {timestamp, output, type}."""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return [raw]
    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                txt = item.get("output") or item.get("message") or ""
                if txt:
                    out.append(str(txt).rstrip("\n"))
            elif isinstance(item, str):
                out.append(item)
    return out


def _annotate(d: dict) -> dict:
    """Attach parsed logs + failure_summary to a deployment dict."""
    raw_logs = d.get("logs") or []
    parsed = parse_log_lines(raw_logs)
    d["parsed_logs"] = parsed
    d["log_counts"] = {
        "total": len(parsed),
        "error": sum(1 for x in parsed if x["severity"] == "error"),
        "warning": sum(1 for x in parsed if x["severity"] == "warning"),
        "info": sum(1 for x in parsed if x["severity"] == "info"),
        "build": sum(1 for x in parsed if x["severity"] == "build"),
        "deploy": sum(1 for x in parsed if x["severity"] == "deploy"),
    }
    if d.get("status") == "failed" and not d.get("failure_summary"):
        d["failure_summary"] = extract_failure_summary(raw_logs)
    return d


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
    return [_annotate(r) for r in rows]


@router.get("/deployments/{deployment_id}")
async def get_deployment(deployment_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    d = await db.deployments.find_one({"id": deployment_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")
    await require_workspace_member(d["workspace_id"], user)
    return _annotate(d)


@router.get("/deployments/{deployment_id}/logs")
async def get_deployment_logs(deployment_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    d = await db.deployments.find_one({"id": deployment_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")
    await require_workspace_member(d["workspace_id"], user)
    raw_logs = d.get("logs", [])
    parsed = parse_log_lines(raw_logs)
    return {
        "logs": raw_logs,
        "parsed_logs": parsed,
        "status": d["status"],
        "failure_summary": d.get("failure_summary") or (extract_failure_summary(raw_logs) if d.get("status") == "failed" else None),
    }


async def _refresh_coolify_logs(deployment_id: str) -> tuple[str, list[str]]:
    """Pull latest Coolify deployment logs for the given local deployment.
    Returns (status, log_lines). If no Coolify uuid bound, returns ("", [])."""
    db = get_db()
    d = await db.deployments.find_one({"id": deployment_id})
    if not d:
        return "", []

    # If we never linked a coolify_deployment_uuid yet, try to find the latest one for the app.
    cool_uuid = d.get("coolify_deployment_uuid")
    if not cool_uuid:
        app = await db.apps.find_one({"id": d["app_id"]})
        if not app or not app.get("coolify_app_uuid") or not coolify.configured:
            return d.get("status", ""), d.get("logs", []) or []
        rows = await coolify.list_deployments(app["coolify_app_uuid"])
        if rows and isinstance(rows, list):
            # Coolify returns newest-first; pick the most recent one started after our row's started_at.
            chosen = rows[0]
            if isinstance(chosen, dict):
                cool_uuid = chosen.get("deployment_uuid") or chosen.get("uuid")
                if cool_uuid:
                    await db.deployments.update_one(
                        {"id": deployment_id},
                        {"$set": {"coolify_deployment_uuid": cool_uuid}},
                    )

    if not cool_uuid or not coolify.configured:
        return d.get("status", ""), d.get("logs", []) or []

    info = await coolify.get_deployment(cool_uuid)
    if not info:
        return d.get("status", ""), d.get("logs", []) or []

    cool_status = (info.get("status") or "").lower()
    new_status = d.get("status") or "building"
    if cool_status in ("finished", "success", "running") or "running" in cool_status:
        new_status = "live"
    elif cool_status in ("failed", "error", "cancelled", "canceled"):
        new_status = "failed"
    elif cool_status in ("in_progress", "queued", "running"):
        new_status = "building"

    log_lines = _parse_coolify_logs(info.get("logs"))

    update = {}
    if new_status != d.get("status"):
        update["status"] = new_status
        if new_status in ("live", "failed"):
            update["finished_at"] = datetime.now(timezone.utc).isoformat()
    if log_lines and log_lines != (d.get("logs") or []):
        update["logs"] = log_lines
    if new_status == "failed":
        summary = extract_failure_summary(log_lines)
        if summary:
            update["failure_summary"] = summary

    if update:
        await db.deployments.update_one({"id": deployment_id}, {"$set": update})
        if "status" in update:
            # also reflect on app
            await db.apps.update_one({"id": d["app_id"]}, {"$set": {"status": update["status"], "last_deploy_at": datetime.now(timezone.utc).isoformat()}})

    return new_status, log_lines or (d.get("logs") or [])


@router.get("/deployments/{deployment_id}/stream")
async def stream_deployment(deployment_id: str, request: Request):
    """SSE stream of the deployment log + status. The Authorization cookie or Bearer token
    secures it; same workspace-member check as other deployment routes.

    Emits events:
      event: line     data: {"text": str, "severity": str}
      event: status   data: {"status": "live"|"failed"|"building", "failure_summary": str|null}
      event: end      data: {"status": "..."}
    """
    user = await get_current_user(request)
    db = get_db()
    d = await db.deployments.find_one({"id": deployment_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Deployment not found")
    await require_workspace_member(d["workspace_id"], user)

    async def gen():
        sent = 0
        # First flush whatever we already have, parsed
        cur_logs = d.get("logs") or []
        for parsed in parse_log_lines(cur_logs):
            yield f"event: line\ndata: {json.dumps(parsed)}\n\n"
            sent += 1

        last_status = d.get("status")
        max_iters = 600  # ~20 minutes
        for _ in range(max_iters):
            if await request.is_disconnected():
                return
            await asyncio.sleep(2.0)
            try:
                status, log_lines = await _refresh_coolify_logs(deployment_id)
            except Exception as e:
                logger.warning("stream refresh failed: %s", e)
                yield f"event: error\ndata: {json.dumps({'error': str(e)[:200]})}\n\n"
                continue

            # Emit only new lines
            if log_lines and len(log_lines) > sent:
                for parsed in parse_log_lines(log_lines[sent:]):
                    yield f"event: line\ndata: {json.dumps(parsed)}\n\n"
                sent = len(log_lines)

            if status and status != last_status:
                last_status = status
                snap = await db.deployments.find_one({"id": deployment_id}, {"_id": 0})
                fail_summary = snap.get("failure_summary") if snap else None
                yield f"event: status\ndata: {json.dumps({'status': status, 'failure_summary': fail_summary})}\n\n"

            if last_status in ("live", "failed", "canceled"):
                break

        snap = await db.deployments.find_one({"id": deployment_id}, {"_id": 0})
        yield f"event: end\ndata: {json.dumps({'status': (snap or {}).get('status', last_status)})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
