"""Web analytics + PageSpeed routes.

* `GET  /api/analytics/tracker.js`  — public tracker (served as JS; CORS *)
* `POST /api/analytics/collect`    — public event ingest (CORS *)
* `GET  /api/apps/{id}/analytics`  — workspace member: summary
* `GET  /api/apps/{id}/analytics/config` — workspace member
* `PUT  /api/apps/{id}/analytics/config` — workspace member: set clarity / auto-inject
* `GET  /api/apps/{id}/analytics/snippet` — workspace member: copy snippet
* `POST /api/apps/{id}/pagespeed/run`     — Pro+: run audit now
* `GET  /api/apps/{id}/pagespeed/latest`  — Pro+: latest run
* `GET  /api/apps/{id}/pagespeed/history` — Pro+: 30-day trend
"""
import os
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from services import analytics as analytics_svc
from services import pagespeed as pagespeed_svc
from services.plans import get_plan

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analytics"])

# Feature flag — flip to True the moment we ship the native heatmap +
# session-replay engine. Until then we don't inject Clarity (or any other
# third-party recording tag) on customer sites, and the customer-facing
# Heatmaps tab shows a "coming soon" placeholder.
HEATMAPS_FEATURE_LIVE = False


# ────────────────── Public tracker script ──────────────────
TRACKER_JS = r"""(function(){
  try {
    var s = document.currentScript;
    var site = (s && s.getAttribute('data-site')) || (window.__DH_SITE__);
    if (!site) return;
    var endpoint = (s && s.getAttribute('data-endpoint')) || '__ENDPOINT__';
    var clarity = (s && s.getAttribute('data-clarity')) || null;

    // Optional Microsoft Clarity loader
    if (clarity && !window.clarity) {
      (function(c,l,a,r,i,t,y){
        c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
        t=l.createElement(r);t.async=1;t.src='https://www.clarity.ms/tag/'+i;
        var y0=l.getElementsByTagName(r)[0];y0.parentNode.insertBefore(t,y0);
      })(window, document, 'clarity', 'script', clarity);
    }

    function send(event, path){
      try {
        var payload = {
          s: site, p: path || (location.pathname + location.search),
          r: document.referrer || null, ev: event,
          lg: navigator.language || null,
          sc: (window.screen ? (screen.width+'x'+screen.height) : null),
        };
        var data = JSON.stringify(payload);
        if (navigator.sendBeacon) {
          var blob = new Blob([data], {type:'application/json'});
          navigator.sendBeacon(endpoint, blob);
        } else {
          fetch(endpoint, {method:'POST', body:data, keepalive:true,
            headers:{'Content-Type':'application/json'}, credentials:'omit'});
        }
      } catch(_){}
    }

    var lastPath = location.pathname + location.search;
    function maybeView(){
      var here = location.pathname + location.search;
      if (here !== lastPath) { lastPath = here; send('pageview', here); }
    }

    // Initial pageview
    send('pageview', lastPath);

    // SPA navigation hooks
    var origPush = history.pushState, origReplace = history.replaceState;
    history.pushState = function(){ var r = origPush.apply(this, arguments); setTimeout(maybeView, 0); return r; };
    history.replaceState = function(){ var r = origReplace.apply(this, arguments); setTimeout(maybeView, 0); return r; };
    window.addEventListener('popstate', maybeView);

    // Outbound clicks
    document.addEventListener('click', function(e){
      var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
      if (!a) return;
      try {
        var u = new URL(a.href, location.href);
        if (u.host && u.host !== location.host) send('outbound', u.href);
      } catch(_){}
    }, {capture:true, passive:true});
  } catch(_){}
})();"""


def _public_base() -> str:
    return (os.environ.get("FRONTEND_URL") or "").rstrip("/")


@router.get("/analytics/tracker.js")
async def tracker_js():
    endpoint = f"{_public_base()}/api/analytics/collect"
    body = TRACKER_JS.replace("__ENDPOINT__", endpoint)
    return PlainTextResponse(
        body, media_type="application/javascript; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=300",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.options("/analytics/collect")
async def collect_preflight():
    return Response(status_code=204, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "86400",
    })


class CollectIn(BaseModel):
    s: str          # site id
    p: Optional[str] = None  # path
    r: Optional[str] = None  # referrer
    ev: Optional[str] = "pageview"
    lg: Optional[str] = None
    sc: Optional[str] = None


@router.post("/analytics/collect")
async def collect(payload: CollectIn, request: Request):
    # Try to source the real client IP + country from edge headers.
    h = request.headers
    xff = h.get("x-forwarded-for", "")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "0.0.0.0")
    country = h.get("cf-ipcountry") or h.get("x-vercel-ip-country") or h.get("x-country") or None
    ua = h.get("user-agent", "")
    res = await analytics_svc.track_event(
        site_id=payload.s, path=payload.p or "/", referrer=payload.r,
        user_agent=ua, language=payload.lg, screen=payload.sc,
        event=payload.ev or "pageview", ip=ip, country=country,
    )
    # Always reply 204 to avoid telegraphing tracking status to clients.
    return Response(
        status_code=204,
        headers={"Access-Control-Allow-Origin": "*",
                 "X-DH-Accepted": "1" if res.get("accepted") else "0"},
    )


# ────────────────── Auth helpers ──────────────────
async def _load_app(app_id: str, request: Request) -> tuple[dict, dict, dict, dict]:
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    ws = await db.workspaces.find_one({"id": app["workspace_id"]}, {"_id": 0, "owner_id": 1}) or {}
    owner = await db.users.find_one({"id": ws.get("owner_id")}, {"_id": 0, "plan": 1}) or {}
    plan = await get_plan(owner.get("plan") or "free") or {}
    return user, app, ws, plan


def _features(plan: dict) -> dict:
    return (plan or {}).get("features_block") or {}


# ────────────────── Analytics endpoints ──────────────────
@router.get("/apps/{app_id}/web-analytics/config")
async def get_app_analytics_config(app_id: str, request: Request):
    _, app, _, plan = await _load_app(app_id, request)
    site_id = await analytics_svc.ensure_site_id(app_id)
    cfg = await analytics_svc.get_config(app_id)
    fe = _public_base()
    # Heatmaps are not yet shipped — see HEATMAPS_FEATURE_LIVE comment at
    # top of this file. We only auto-inject the recording tag once the
    # native engine is live, the platform admin enabled it, and the plan
    # unlocks the feature. Until then: clean first-party snippet only.
    feats = _features(plan)
    inject_clarity = bool(
        HEATMAPS_FEATURE_LIVE
        and cfg.get("clarity_project_id")
        and feats.get("heatmaps")
    )
    snippet = (f'<script defer data-site="{site_id}" '
               f'data-endpoint="{fe}/api/analytics/collect"'
               + (f' data-clarity="{cfg["clarity_project_id"]}"' if inject_clarity else "")
               + f' src="{fe}/api/analytics/tracker.js"></script>')
    # Pre-filtered deeplink scoped to this app's primary host — only useful
    # while the recording integration is live; suppressed otherwise.
    clarity_deeplink = None
    if inject_clarity and app.get("primary_url"):
        from urllib.parse import urlparse, quote
        host = urlparse(app["primary_url"]).hostname or ""
        if host:
            clarity_deeplink = (
                f"https://clarity.microsoft.com/projects/view/{cfg['clarity_project_id']}"
                f"/dashboard?filters=URL+contains+{quote(host)}"
            )
    return {
        "site_id": site_id,
        "heatmaps_active": inject_clarity,
        "heatmaps_coming_soon": not HEATMAPS_FEATURE_LIVE,
        "platform_clarity_configured": cfg.get("platform_clarity_configured", False),
        "clarity_deeplink": clarity_deeplink,
        "auto_inject_enabled": cfg.get("auto_inject_enabled", False),
        "snippet": snippet,
        "tracker_url": f"{fe}/api/analytics/tracker.js",
        "collect_url": f"{fe}/api/analytics/collect",
        "primary_url": app.get("primary_url"),
        "features": feats,
        "plan_id": (plan or {}).get("id"),
    }


class AnalyticsConfigIn(BaseModel):
    auto_inject_enabled: Optional[bool] = None


@router.put("/apps/{app_id}/web-analytics/config")
async def put_app_analytics_config(app_id: str, payload: AnalyticsConfigIn, request: Request):
    await _load_app(app_id, request)
    if payload.auto_inject_enabled is not None:
        await analytics_svc.set_auto_inject(app_id, payload.auto_inject_enabled)
    return await get_app_analytics_config(app_id, request)


@router.get("/apps/{app_id}/web-analytics")
async def get_app_analytics(app_id: str, request: Request, window: str = "7d"):
    await _load_app(app_id, request)
    return await analytics_svc.summary(app_id, window=window)


# ────────────────── PageSpeed endpoints ──────────────────
def _require_pagespeed(plan: dict) -> None:
    if not _features(plan).get("pagespeed"):
        raise HTTPException(status_code=402,
                            detail="Speed Insights require the Pro plan or higher.")


@router.get("/apps/{app_id}/pagespeed/latest")
async def pagespeed_latest(app_id: str, request: Request):
    _, _, _, plan = await _load_app(app_id, request)
    _require_pagespeed(plan)
    run = await pagespeed_svc.latest_for_app(app_id)
    return {"have_data": bool(run), "run": run}


@router.get("/apps/{app_id}/pagespeed/history")
async def pagespeed_history(app_id: str, request: Request, days: int = 30):
    _, _, _, plan = await _load_app(app_id, request)
    _require_pagespeed(plan)
    rows = await pagespeed_svc.history_for_app(app_id, days=days)
    return {"window_days": days, "rows": rows}


@router.post("/apps/{app_id}/pagespeed/run")
async def pagespeed_run(app_id: str, request: Request):
    _, _, _, plan = await _load_app(app_id, request)
    _require_pagespeed(plan)
    res = await pagespeed_svc.run_for_app(app_id, manual=True)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "audit failed"))
    return res["run"]
