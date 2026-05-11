"""Incoming GitHub webhook handler — auto-deploy on push.

Endpoint: POST /api/webhooks/github/{app_id}
  - Verifies HMAC-SHA256 signature using the app's stored `webhook_secret`.
  - Reads the `push` event payload.
  - Compares `ref` against the app's configured branch.
  - On match: enqueues a redeploy via the existing _redeploy_background task.

Returns:
  202 — accepted (deploy queued)
  204 — ignored (different branch, ping, etc.)
  401 — signature mismatch / missing
  404 — unknown app or no webhook secret on this app
"""
import hmac
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Header
from typing import Optional

from db import get_db
from routers.apps import _redeploy_background

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _verify_signature(secret: str, body: bytes, sig_header: Optional[str]) -> bool:
    """GitHub sends `X-Hub-Signature-256: sha256=<hex>`. Constant-time compare."""
    if not secret or not sig_header:
        return False
    if not sig_header.startswith("sha256="):
        return False
    expected = sig_header.split("=", 1)[1].strip()
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)


@router.post("/webhooks/github/{app_id}", status_code=202)
async def github_webhook(
    app_id: str,
    request: Request,
    background: BackgroundTasks,
    x_github_event: Optional[str] = Header(default=None),
    x_hub_signature_256: Optional[str] = Header(default=None),
):
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="app not found")
    secret = app.get("webhook_secret")
    if not secret:
        raise HTTPException(status_code=404, detail="webhook not configured for this app")

    body = await request.body()
    if not _verify_signature(secret, body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="invalid signature")

    # Acknowledge GitHub pings even if disabled — they only validate reachability.
    if (x_github_event or "").lower() == "ping":
        return {"status": "pong"}

    if not app.get("webhook_enabled", True):
        return {"status": "disabled"}

    if (x_github_event or "").lower() != "push":
        return {"status": "ignored", "reason": f"event={x_github_event}"}

    payload = await request.json()
    ref = (payload or {}).get("ref") or ""  # e.g. "refs/heads/main"
    pushed_branch = ref.split("/", 2)[-1] if ref.startswith("refs/heads/") else ""
    app_branch = (app.get("branch") or "main").strip()
    if not pushed_branch or pushed_branch != app_branch:
        return {"status": "ignored", "reason": f"branch={pushed_branch}, configured={app_branch}"}

    head_commit = (payload or {}).get("head_commit") or {}
    commit_sha = head_commit.get("id")
    commit_message = head_commit.get("message") or "git push"
    pusher = ((payload or {}).get("pusher") or {}).get("name") or "github"

    # Queue a redeploy through the same pipeline as a manual one.
    deployment_id = str(uuid.uuid4())
    await db.deployments.insert_one({
        "id": deployment_id,
        "app_id": app_id,
        "workspace_id": app["workspace_id"],
        "status": "queued",
        "commit_sha": commit_sha,
        "commit_message": commit_message,
        "branch": app_branch,
        "trigger": "webhook",
        "trigger_actor": pusher,
        "logs": [f"[QUEUE] webhook push from @{pusher} ({commit_sha[:7] if commit_sha else 'unknown'})"],
        "started_at": _now_iso(),
        "finished_at": None,
    })

    coolify_uuid = app.get("coolify_app_uuid")
    if not coolify_uuid:
        # First deploy never finished — fall back to creating the app from
        # scratch via _coolify_deploy. The redeploy path needs a Coolify UUID.
        from routers.apps import _coolify_deploy
        background.add_task(_coolify_deploy, app_id, deployment_id)
    else:
        background.add_task(_redeploy_background, app_id, deployment_id, coolify_uuid, None)

    return {"status": "queued", "deployment_id": deployment_id, "branch": app_branch}
