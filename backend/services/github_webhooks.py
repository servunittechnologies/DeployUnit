"""GitHub webhooks — auto-deploy on `git push`.

Per-app, we:
  1. Generate a random `webhook_secret` (hex) on app create.
  2. Register a webhook at `https://api.github.com/repos/{owner}/{repo}/hooks`
     pointing at `<our backend>/api/webhooks/github/{app_id}` with HMAC-SHA256
     signature using `webhook_secret`.
  3. On push events to the app's configured branch, trigger a redeploy.

Fields persisted on `apps`:
  webhook_secret:    str (hex)
  webhook_github_id: int (the hook id returned by GitHub; needed to delete)
  webhook_enabled:   bool
  webhook_url:       str (full public URL we registered)

Failures degrade gracefully — if no GH OAuth token or the API rejects us,
the app still works (user can fall back to a manual hook).
"""
import os
import logging
import secrets
from typing import Optional

import httpx

from services.github_helpers import parse_repo, workspace_github_token

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def generate_secret() -> str:
    """Return a 64-char hex secret suitable for GitHub webhook signing."""
    return secrets.token_hex(32)


def public_webhook_url(app_id: str) -> str:
    """The publicly reachable URL GitHub will POST to."""
    base = (
        os.environ.get("PUBLIC_BACKEND_URL")
        or os.environ.get("FRONTEND_URL")  # backend lives behind the same ingress; /api/* routes to backend
        or ""
    ).rstrip("/")
    return f"{base}/api/webhooks/github/{app_id}"


async def register_webhook(*, app: dict, workspace_id: str) -> Optional[dict]:
    """Create a GitHub webhook for `app['repo_url']`. Returns dict with
    {id, secret, url} on success. Idempotent-ish: if a hook with the same URL
    already exists we delete it first."""
    parsed = parse_repo(app.get("repo_url") or "")
    if not parsed:
        return None
    owner, repo = parsed
    token = await workspace_github_token(workspace_id)
    if not token:
        logger.info("github webhook: no token for workspace %s; skipping", workspace_id)
        return None
    hook_url = public_webhook_url(app["id"])
    if not hook_url.startswith("https://"):
        logger.warning("github webhook: PUBLIC_BACKEND_URL not https; skipping")
        return None
    secret = app.get("webhook_secret") or generate_secret()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "name": "web",
        "active": True,
        "events": ["push"],
        "config": {
            "url": hook_url,
            "content_type": "json",
            "secret": secret,
            "insecure_ssl": "0",
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            # Clean up any prior hook pointing at the same URL (e.g. after a
            # rotation) so we don't end up with duplicate registrations.
            existing = await cli.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/hooks", headers=headers
            )
            if existing.status_code == 200:
                for h in existing.json() or []:
                    if (h.get("config") or {}).get("url") == hook_url:
                        await cli.delete(
                            f"{GITHUB_API}/repos/{owner}/{repo}/hooks/{h['id']}",
                            headers=headers,
                        )
            r = await cli.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/hooks",
                headers=headers, json=payload,
            )
        if r.status_code >= 400:
            logger.warning("github webhook register %s/%s -> %s %s",
                           owner, repo, r.status_code, r.text[:300])
            return None
        body = r.json()
        return {"id": body.get("id"), "secret": secret, "url": hook_url}
    except Exception as e:
        logger.warning("github webhook register failed: %s", e)
        return None


async def unregister_webhook(*, app: dict, workspace_id: str) -> bool:
    """Remove the webhook from GitHub. Idempotent — safe to call when nothing
    is registered."""
    hook_id = app.get("webhook_github_id")
    if not hook_id:
        return True
    parsed = parse_repo(app.get("repo_url") or "")
    if not parsed:
        return False
    owner, repo = parsed
    token = await workspace_github_token(workspace_id)
    if not token:
        return False
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.delete(
                f"{GITHUB_API}/repos/{owner}/{repo}/hooks/{hook_id}",
                headers=headers,
            )
        return r.status_code in (200, 204, 404)
    except Exception as e:
        logger.warning("github webhook unregister failed: %s", e)
        return False
