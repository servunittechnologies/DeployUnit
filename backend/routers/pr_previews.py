"""PR Preview Deploys — read API for the AppDetail UI.

Lifecycle is managed by GitHub webhooks (services/pr_previews.py). This
router only exposes list/delete for visibility.
"""
from fastapi import APIRouter, HTTPException, Request

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from services.pr_previews import _teardown_preview

router = APIRouter(tags=["pr-previews"])


@router.get("/apps/{app_id}/pr-previews")
async def list_pr_previews(app_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    rows = await db.pr_previews.find(
        {"parent_app_id": app_id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(100)
    return {"previews": rows, "parent_app_id": app_id}


@router.delete("/apps/{app_id}/pr-previews/{preview_id}")
async def teardown_pr_preview(app_id: str, preview_id: str, request: Request):
    """Manual teardown — useful when the PR was closed before the webhook
    fired (or if the user wants to recycle resources early)."""
    user = await get_current_user(request)
    db = get_db()
    preview = await db.pr_previews.find_one({"id": preview_id, "parent_app_id": app_id}, {"_id": 0})
    if not preview:
        raise HTTPException(status_code=404, detail="Preview not found")
    await require_workspace_member(preview["workspace_id"], user, ["owner", "admin", "developer"])
    await _teardown_preview(preview)
    return {"torn_down": True}
