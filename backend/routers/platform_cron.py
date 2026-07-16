"""Vercel Cron endpoints for the periodic platform jobs.

On an always-on host these run via the in-process APScheduler (see server.py).
On Vercel serverless there is no persistent scheduler, so Vercel Cron calls
these endpoints instead. Each bucket runs a group of jobs; every job is wrapped
so one failure never blocks the rest.

Auth: Vercel Cron sends `Authorization: Bearer $CRON_SECRET` when the CRON_SECRET
env var is set — we require it. (Also accepts Vercel's `x-vercel-cron` header.)

Frequency caveat: Vercel Cron's minimum interval is 1 minute (Pro plan), so the
sub-minute native jobs (deploy sync 15s, watchdog/verify 30s) run at most once a
minute here. For true real-time behaviour run an always-on worker (worker.py)
instead — see DEPLOY.md.
"""

import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException, Request

from workers.monitor import run_monitor_tick, sync_deployments, deployment_watchdog, status_sampler
from services.credits import monthly_grant_tick
from services.resources import charge_due_addons
from services.metrics import downsample_and_gc
from services.pagespeed import daily_pagespeed_tick
from services.analytics import gc as analytics_gc
from services.subdomains import refill_pool as subdomain_refill_pool
from services.routing_healer import routing_healer_tick
from services.coolify_reconcile import reconcile_tick as coolify_reconcile_tick
from services.custom_subdomain import verify_pending_subdomains_tick
from services.health_audit import health_audit_tick
from services.app_addons import renew_tick as app_addons_renew_tick
from routers.app_addons import heatmap_gc_tick
from routers.status import status_ping_tick

router = APIRouter(prefix="/cron", tags=["cron"])
logger = logging.getLogger("deployunit.cron")

# Jobs grouped by how often they should run. Names are for logging only.
FREQUENT = [
    ("monitor", run_monitor_tick),
    ("deploy_sync", sync_deployments),
    ("deploy_watchdog", deployment_watchdog),
    ("status_ping", status_ping_tick),
    ("routing_healer", routing_healer_tick),
    ("subdomain_pool_refill", subdomain_refill_pool),
    ("custom_subdomain_verify", verify_pending_subdomains_tick),
    ("status_sampler", status_sampler),
    ("coolify_reconcile", coolify_reconcile_tick),
]
HOURLY = [
    ("credits_grant", monthly_grant_tick),
    ("resource_billing", charge_due_addons),
    ("metrics_rollup", downsample_and_gc),
    ("app_addons_renew", app_addons_renew_tick),
]
DAILY = [
    ("pagespeed_daily", daily_pagespeed_tick),
    ("analytics_gc", analytics_gc),
    ("health_audit", health_audit_tick),
    ("heatmap_gc", heatmap_gc_tick),
]


def _authorize(request: Request) -> None:
    secret = os.environ.get("CRON_SECRET", "")
    if not secret:
        # No secret configured → only allow Vercel's own cron invocations.
        if request.headers.get("x-vercel-cron"):
            return
        raise HTTPException(status_code=403, detail="CRON_SECRET not configured")
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {secret}" and not request.headers.get("x-vercel-cron"):
        raise HTTPException(status_code=403, detail="Forbidden")


async def _run_group(name: str, jobs) -> dict:
    results = {}
    for job_name, fn in jobs:
        try:
            res = fn()
            if asyncio.iscoroutine(res):
                await res
            results[job_name] = "ok"
        except Exception as e:  # noqa: BLE001 — one bad job must not block the rest
            logger.warning("cron %s: %s failed: %s", name, job_name, e)
            results[job_name] = f"error: {str(e)[:120]}"
    return {"group": name, "ran": results}


@router.get("/frequent")
async def cron_frequent(request: Request):
    _authorize(request)
    return await _run_group("frequent", FREQUENT)


@router.get("/hourly")
async def cron_hourly(request: Request):
    _authorize(request)
    return await _run_group("hourly", HOURLY)


@router.get("/daily")
async def cron_daily(request: Request):
    _authorize(request)
    return await _run_group("daily", DAILY)
