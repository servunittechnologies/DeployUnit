"""Per-app paid add-on endpoints + in-house Site Heatmaps collector + viewer.

Three responsibilities split into one router because they're all tied to
`/api/apps/{id}` and share the addon-active gating:

  GET  /api/apps/{id}/addons                  -> list per-app subscriptions
  POST /api/apps/{id}/addons/{addon}/enable   -> charge first month, activate
  POST /api/apps/{id}/addons/{addon}/cancel   -> mark for non-renewal

  POST /api/heatmaps/collect                  -> public ingestion (no auth)
  GET  /api/heatmaps/snippet.js               -> public JS that the user
                                                  pastes into their site
  GET  /api/apps/{id}/heatmaps/pages          -> aggregated pages with counts
  GET  /api/apps/{id}/heatmaps/page           -> events for one URL
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from auth_utils import get_current_user, require_workspace_member
from db import get_db
from services.app_addons import (
    ADDON_CATALOG, enable_addon, cancel_addon, list_for_app, is_active,
)
from services.audit import log as audit_log

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────── Subscription endpoints ───────────────────────


@router.get("/apps/{app_id}/addons")
async def addons_list(app_id: str, request: Request):
    """Catalog + current state for every supported add-on on this app.
    The UI uses this to render the toggle for each card."""
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    subs_by_id = {s["addon_id"]: s for s in await list_for_app(app_id)}
    out = []
    for aid, cat in ADDON_CATALOG.items():
        sub = subs_by_id.get(aid)
        out.append({
            "id": aid,
            "display_name": cat["display_name"],
            "description": cat["description"],
            "cost_cr_month": cat["cost_cr_month"],
            "active": bool(sub and sub.get("status") in ("active", "grace", "cancelled") and sub.get("expires_at", "") > datetime.now(timezone.utc).isoformat()),
            "subscription": sub,
        })
    return out


@router.post("/apps/{app_id}/addons/{addon_id}/enable")
async def addon_enable(app_id: str, addon_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "billing"])
    sub = await enable_addon(app, addon_id, actor_user_id=user["id"])
    audit_log(action="app.addon_enable", actor=user,
              resource_type="app", resource_id=app_id,
              meta={"addon": addon_id}, request=request)
    return sub


@router.post("/apps/{app_id}/addons/{addon_id}/cancel")
async def addon_cancel(app_id: str, addon_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "billing"])
    res = await cancel_addon(app_id, addon_id)
    audit_log(action="app.addon_cancel", actor=user,
              resource_type="app", resource_id=app_id,
              meta={"addon": addon_id}, request=request)
    return res


# ─────────────────────────── Heatmap collector ───────────────────────────


# Allowed event types. Anything else gets 400'd to keep the collection clean.
HEATMAP_EVENT_TYPES = {"click", "scroll", "move", "rage", "view"}
# Per-event-type sampling — most heatmap pixels come from `move` events
# which would balloon the collection. We sample 1-in-N at the *server* so
# the snippet stays small (~1.2KB). Tune by env if needed.
SAMPLING = {"click": 1, "scroll": 1, "rage": 1, "view": 1, "move": 5}
# Hard caps per app to prevent a runaway script from filling the DB.
MAX_EVENTS_PER_DAY_PER_APP = 200_000


_URL_PATH_RE = re.compile(r"^[/\w\-./?#=&%:+@!~*$,;()]{1,500}$")


class HeatmapCollect(BaseModel):
    app: str = Field(..., min_length=8, max_length=64, description="App id")
    url: str = Field(..., min_length=1, max_length=500)
    type: Literal["click", "scroll", "move", "rage", "view"]
    x: int | None = Field(None, ge=-10_000, le=10_000)
    y: int | None = Field(None, ge=-10_000, le=10_000)
    w: int | None = Field(None, ge=0, le=10_000, description="viewport width")
    h: int | None = Field(None, ge=0, le=20_000, description="document height / scroll depth")
    s: str | None = Field(None, max_length=40, description="anonymous session id")


@router.post("/heatmaps/collect")
async def heatmaps_collect(payload: HeatmapCollect, request: Request):
    """Public ingestion endpoint. Validates that the app has the heatmaps
    addon active before persisting — otherwise it silently 204s so a
    forgotten snippet on a cancelled site doesn't return errors in the
    browser console."""
    if not _URL_PATH_RE.match(payload.url):
        return Response(status_code=204)
    if not await is_active(payload.app, "heatmaps"):
        return Response(status_code=204)

    db = get_db()
    # Sampling — drop every Nth event server-side instead of client-side
    # so we can tune ratios without a snippet redeploy.
    sample_n = SAMPLING.get(payload.type, 1)
    if sample_n > 1:
        # Mix in a cheap pseudo-random based on session+timestamp.
        seed = abs(hash((payload.s or "", str(payload.x), str(payload.y), payload.type))) % sample_n
        if seed != 0:
            return Response(status_code=204)

    # Day-based hard cap — only sample after a quick estimate. We use the
    # collection size for the past hour as a proxy so the check doesn't
    # add a full count_documents to every request.
    today = datetime.now(timezone.utc).date().isoformat()
    quota_doc = await db.heatmap_quotas.find_one(
        {"app_id": payload.app, "day": today}, {"_id": 0, "count": 1}
    )
    if quota_doc and quota_doc.get("count", 0) >= MAX_EVENTS_PER_DAY_PER_APP:
        return Response(status_code=204)

    # Resolve the workspace_id once so the events table is partitionable.
    app = await db.apps.find_one({"id": payload.app}, {"_id": 0, "workspace_id": 1})
    if not app:
        return Response(status_code=204)

    await db.heatmap_events.insert_one({
        "id": str(uuid.uuid4()),
        "app_id": payload.app,
        "workspace_id": app["workspace_id"],
        "url": payload.url,
        "type": payload.type,
        "x": payload.x or 0,
        "y": payload.y or 0,
        "w": payload.w or 0,
        "h": payload.h or 0,
        "s": payload.s,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    await db.heatmap_quotas.update_one(
        {"app_id": payload.app, "day": today},
        {"$inc": {"count": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return Response(status_code=204)


# ─────────────────────────── Heatmap snippet ───────────────────────────


_SNIPPET_TEMPLATE = """
/* DeployUnit heatmap snippet - in-house, no third party */
(function(){
  var APP = "__APP_ID__";
  var BASE = "__BASE_URL__";
  if (window.__deployunit_heatmap_loaded__) return;
  window.__deployunit_heatmap_loaded__ = true;
  var SID = "h_" + Math.random().toString(36).slice(2) + "_" + Date.now();
  var URL = location.pathname + location.search;
  var send = function(e) {
    try {
      navigator.sendBeacon(BASE + "/api/heatmaps/collect",
        new Blob([JSON.stringify(e)], {type:"application/json"}));
    } catch (_) {}
  };
  send({app:APP, url:URL, type:"view",
        w: innerWidth, h: document.documentElement.scrollHeight, s:SID});
  var lastClick = 0;
  addEventListener("click", function(ev){
    var now = Date.now();
    if (ev.target && now - lastClick < 60) {
      send({app:APP, url:URL, type:"rage",
            x:ev.pageX, y:ev.pageY, w:innerWidth, s:SID});
    }
    lastClick = now;
    send({app:APP, url:URL, type:"click",
          x:ev.pageX, y:ev.pageY, w:innerWidth, s:SID});
  }, true);
  var lastScroll = 0;
  addEventListener("scroll", function(){
    var now = Date.now();
    if (now - lastScroll < 1000) return; lastScroll = now;
    send({app:APP, url:URL, type:"scroll",
          y: scrollY + innerHeight,
          w: innerWidth, h: document.documentElement.scrollHeight, s:SID});
  }, {passive:true});
  var moveT = 0;
  addEventListener("mousemove", function(ev){
    var now = Date.now();
    if (now - moveT < 250) return; moveT = now;
    send({app:APP, url:URL, type:"move",
          x:ev.pageX, y:ev.pageY, w:innerWidth, s:SID});
  }, {passive:true});
})();
"""


@router.get("/heatmaps/snippet.js")
async def heatmaps_snippet(app: str, request: Request):
    """Serves the tracking snippet. We bake the app_id into the response so
    the user just adds ONE `<script src="...snippet.js?app=APP_ID">` tag
    to their site — no separate config block needed.

    The base URL the snippet POSTs to is read from the admin-configured
    `platform_settings.public_base_url` (set on the Platform Domain tab) so
    we always emit the proper *external* hostname, not whatever internal
    K8s host happens to be in `request.base_url`."""
    if not re.match(r"^[a-f0-9-]{8,64}$", app):
        return Response(content="/* invalid app id */", media_type="application/javascript", status_code=400)
    db = get_db()
    settings = await db.platform_settings.find_one(
        {"id": "platform-singleton"},
        {"_id": 0, "public_base_url": 1, "platform_root_domain": 1},
    ) or {}
    base = (settings.get("public_base_url") or "").rstrip("/")
    if not base and settings.get("platform_root_domain"):
        base = f"https://{settings['platform_root_domain']}"
    if not base:
        base = str(request.base_url).rstrip("/")
        if base.endswith("/api"):
            base = base[:-4]
    js = _SNIPPET_TEMPLATE.replace("__APP_ID__", app).replace("__BASE_URL__", base)
    return Response(
        content=js, media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─────────────────────────── Heatmap viewer (dashboard) ───────────────────


@router.get("/apps/{app_id}/heatmaps/pages")
async def heatmaps_pages(app_id: str, request: Request, days: int = 30):
    """List every URL we've seen events on for this app + a count per
    event type. Used by the dashboard 'pick a page to visualize' picker."""
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0, "workspace_id": 1})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, min(90, days)))).isoformat()
    pipeline = [
        {"$match": {"app_id": app_id, "ts": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$url",
            "total": {"$sum": 1},
            "clicks": {"$sum": {"$cond": [{"$eq": ["$type", "click"]}, 1, 0]}},
            "rage":   {"$sum": {"$cond": [{"$eq": ["$type", "rage"]}, 1, 0]}},
            "views":  {"$sum": {"$cond": [{"$eq": ["$type", "view"]}, 1, 0]}},
            "scrolls":{"$sum": {"$cond": [{"$eq": ["$type", "scroll"]}, 1, 0]}},
            "last_ts": {"$max": "$ts"},
        }},
        {"$sort": {"total": -1}},
        {"$limit": 200},
    ]
    pages = []
    async for row in db.heatmap_events.aggregate(pipeline):
        pages.append({
            "url": row["_id"], "total": row["total"], "clicks": row["clicks"],
            "rage": row["rage"], "views": row["views"], "scrolls": row["scrolls"],
            "last_ts": row["last_ts"],
        })
    return {"days": days, "pages": pages, "is_active": await is_active(app_id, "heatmaps")}


@router.get("/apps/{app_id}/heatmaps/page")
async def heatmaps_page(app_id: str, url: str, request: Request,
                        days: int = 30, limit: int = 5000,
                        type: Optional[str] = None):
    """Return the raw click/scroll/rage points for one URL so the dashboard
    can render the heatmap canvas. Capped at `limit` newest events.

    Returned data is intentionally minimal (x, y, w, type) — no IPs, no
    session-level info — so this is privacy-friendly out of the box.
    """
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0, "workspace_id": 1})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, min(90, days)))).isoformat()
    q: dict = {"app_id": app_id, "url": url, "ts": {"$gte": cutoff}}
    if type and type in HEATMAP_EVENT_TYPES:
        q["type"] = type
    events = await db.heatmap_events.find(
        q, {"_id": 0, "x": 1, "y": 1, "w": 1, "h": 1, "type": 1, "ts": 1},
    ).sort("ts", -1).limit(min(20_000, max(100, limit))).to_list(limit)
    # Compute viewport-bucketed click frequency so the canvas can render a
    # weighted heatmap.
    return {"url": url, "days": days, "count": len(events), "events": events}


# ─────────────────────────── Cleanup tick ───────────────────────────


async def heatmap_gc_tick() -> dict:
    """Drop heatmap events older than the per-app retention (7d default,
    30d with the log-retention addon — heatmaps are technically "log"
    data so they share retention)."""
    db = get_db()
    from services.app_addons import active_app_ids
    paid_apps = await active_app_ids("log-retention")
    now = datetime.now(timezone.utc)
    short_cut = (now - timedelta(days=7)).isoformat()
    long_cut = (now - timedelta(days=30)).isoformat()
    # 1) Universal ceiling — drop anything older than 30 days
    r1 = await db.heatmap_events.delete_many({"ts": {"$lt": long_cut}})
    # 2) For apps WITHOUT the addon, drop anything older than 7 days
    r2_count = 0
    if True:
        # Build the negation efficiently — exclude paid apps from the query
        q = {"ts": {"$lt": short_cut}}
        if paid_apps:
            q["app_id"] = {"$nin": list(paid_apps)}
        r2 = await db.heatmap_events.delete_many(q)
        r2_count = r2.deleted_count
    # Trim quota cache > 60 days
    await db.heatmap_quotas.delete_many({"day": {"$lt": (now - timedelta(days=60)).date().isoformat()}})
    return {"hard_cut_dropped": r1.deleted_count, "tier_cut_dropped": r2_count,
            "paid_apps": len(paid_apps)}
