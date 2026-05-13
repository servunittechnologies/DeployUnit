"""Auto-inject preflight + result-callback endpoints.

  * GET  /api/auto-inject/preflight.js?app=<id>&token=<hmac>
        Returns the Node preflight script the build container downloads
        and pipes to `node -`. Public endpoint, HMAC-token-gated to a
        specific app id so a leaked URL can't be replayed.
  * POST /api/auto-inject/result?app=<id>&token=<hmac>
        Build container reports the injection outcome. Stored on the
        app's analytics-config row so the dashboard can show it.
  * POST /api/apps/{app_id}/auto-inject/toggle
        Workspace-member endpoint to flip the auto-inject flag.
  * POST /api/apps/{app_id}/auto-inject/dry-run
        Returns the rendered build_command that would be used on the
        next deploy (so the UI can show the exact wrap users get).
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response

from auth_utils import get_current_user, require_workspace_member
from clients.coolify import coolify
from db import get_db
from services.analytics import set_auto_inject, ensure_site_id
from services.audit import log as audit_log
from services.auto_injector import (
    render_preflight_js,
    verify_token,
    wrap_build_command,
    unwrap_build_command,
    record_result,
    get_last_result,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auto-inject"])


# ───────────────────── Public (build container) ─────────────────────


@router.get("/auto-inject/preflight.js")
async def preflight_script(app: str = Query(...), token: str = Query(...)):
    """Serve the framework-detecting preflight script. Token is HMAC of
    the app id — verifies the requester is allowed to fetch this specific
    app's snippet. Anyone with both the app id AND the token gets the
    script (which only contains the public analytics snippet anyway)."""
    return await _serve_preflight(app, token)


@router.get("/aij/{app_id}/{token}")
async def preflight_script_short(app_id: str, token: str):
    """Compact alias for /auto-inject/preflight.js — used by the build
    container because the full URL would push the wrapped build_command
    over Coolify v4's 255-char limit.
    `aij` = `auto-inject`."""
    return await _serve_preflight(app_id, token)


async def _serve_preflight(app: str, token: str):
    if not verify_token(app, token):
        raise HTTPException(status_code=403, detail="Bad token")
    db = get_db()
    a = await db.apps.find_one({"id": app}, {"_id": 0, "id": 1})
    if not a:
        raise HTTPException(status_code=404, detail="App not found")
    site_id = await ensure_site_id(app)
    import os
    fe = (os.environ.get("FRONTEND_URL")
          or os.environ.get("PUBLIC_FRONTEND_URL")
          or os.environ.get("REACT_APP_BACKEND_URL")
          or "https://deployunit.com").rstrip("/")
    snippet_url = f"{fe}/api/analytics/tracker.js"
    collect_url = f"{fe}/api/analytics/collect"
    js = render_preflight_js(
        app_id=app,
        site_id=site_id,
        snippet_url=snippet_url,
        collect_url=collect_url,
    )
    return Response(content=js, media_type="application/javascript")


@router.post("/auto-inject/result")
async def report_result(
    request: Request,
    app: str = Query(...),
    token: str = Query(...),
):
    """Build container POSTs the outcome here. We persist it so the
    Setup tab can show the last-injection status to the user."""
    if not verify_token(app, token):
        raise HTTPException(status_code=403, detail="Bad token")
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    saved = await record_result(app, payload or {})
    return {"ok": True, "saved": saved}


# ───────────────────── Owner-facing toggle + status ─────────────────────


@router.post("/apps/{app_id}/auto-inject/toggle")
async def toggle_auto_inject(app_id: str, request: Request):
    """Flip the auto-inject flag for this app. Also updates the live
    Coolify build_command so the next deploy picks it up immediately —
    no extra clicks needed.

    Body: { "enabled": bool }  (defaults to !current_state if omitted)
    """
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])

    try:
        body = await request.json()
    except Exception:
        body = {}
    cur = await db.app_analytics_config.find_one(
        {"app_id": app_id}, {"_id": 0, "auto_inject_enabled": 1}
    )
    enabled = body.get("enabled")
    if enabled is None:
        enabled = not bool((cur or {}).get("auto_inject_enabled"))
    enabled = bool(enabled)

    await set_auto_inject(app_id, enabled)

    # Sync the Coolify build_command so it takes effect on the next deploy.
    base = app.get("build_command") or ""
    new_cmd = wrap_build_command(app_id, base) if enabled else unwrap_build_command(
        app.get("_active_build_command") or base
    )
    # Save the user's RAW build_command on our row (never the wrapped one) so
    # round-tripping toggles never drifts. We separately track the wrapped
    # version on `_active_build_command` for Coolify sync.
    await db.apps.update_one(
        {"id": app_id},
        {"$set": {"_active_build_command": new_cmd, "auto_inject_enabled": enabled}},
    )
    if app.get("coolify_app_uuid"):
        try:
            await coolify.update_application(app["coolify_app_uuid"], {"build_command": new_cmd})
        except Exception as e:
            logger.warning("auto-inject toggle: coolify PATCH failed for %s: %s", app_id, e)

    audit_log(
        action="app.auto_inject_toggle",
        actor=user,
        workspace_id=app["workspace_id"],
        resource_type="app",
        resource_id=app_id,
        meta={"enabled": enabled},
        request=request,
    )
    return {"enabled": enabled, "active_build_command": new_cmd}


@router.get("/apps/{app_id}/auto-inject")
async def get_auto_inject_state(app_id: str, request: Request):
    """Combined state: flag + last injection outcome + the build command
    we will actually run + the LIVE build_command Coolify currently has
    stored (so the user can verify the PATCH actually landed)."""
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    enabled = bool(
        (await db.app_analytics_config.find_one(
            {"app_id": app_id}, {"_id": 0, "auto_inject_enabled": 1}
        ) or {}).get("auto_inject_enabled")
    )
    last = await get_last_result(app_id) or None
    base = app.get("build_command") or ""
    active = app.get("_active_build_command") or (wrap_build_command(app_id, base) if enabled else base)

    # Read the LIVE build_command from Coolify so the UI can show whether
    # our PATCH actually landed there. This makes silent build-engine
    # overrides immediately visible to the user.
    coolify_build_command = None
    coolify_error = None
    coolify_has_preflight = None
    if app.get("coolify_app_uuid"):
        try:
            live = await coolify.get_application(app["coolify_app_uuid"])
            if isinstance(live, dict):
                coolify_build_command = live.get("build_command") or ""
                coolify_has_preflight = bool(coolify_build_command) and (
                    "/api/aij/" in coolify_build_command or "preflight.js" in coolify_build_command
                )
        except Exception as e:
            coolify_error = str(e)[:200]

    return {
        "enabled": enabled,
        "supported_frameworks": [
            "nextjs-app-router", "nextjs-pages-router", "nuxt3",
            "sveltekit", "astro", "remix", "vite", "cra", "static-html",
        ],
        "user_build_command": base,
        "active_build_command": active,
        "coolify_build_command": coolify_build_command,
        "coolify_has_preflight": coolify_has_preflight,
        "coolify_error": coolify_error,
        "last_result": last,
    }
