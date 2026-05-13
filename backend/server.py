"""DeployUnit API entrypoint."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db import connect, ensure_indexes, disconnect
from seed import seed_initial_data
from workers.monitor import run_monitor_tick, sync_deployments, deployment_watchdog, status_sampler
from services.plans import seed_default_plans
from services.credits import monthly_grant_tick
from services.resources import charge_due_addons
from services.metrics import downsample_and_gc
from services.account_migration import migrate_accounts, needs_migration
from services.pagespeed import daily_pagespeed_tick
from services.analytics import gc as analytics_gc
from services.subdomains import refill_pool as subdomain_refill_pool
from services.routing_healer import routing_healer_tick
from services.coolify_reconcile import reconcile_tick as coolify_reconcile_tick
from services.custom_subdomain import verify_pending_subdomains_tick
from services.health_audit import health_audit_tick
from routers.status import status_ping_tick

from routers import (
    auth as auth_router,
    workspaces as workspaces_router,
    projects as projects_router,
    apps as apps_router,
    deployments as deployments_router,
    domains as domains_router,
    monitoring as monitoring_router,
    alerts as alerts_router,
    billing as billing_router,
    notifications as notifications_router,
    settings as settings_router,
    github as github_router,
    github_oauth as github_oauth_router,
    admin as admin_router,
    credits as credits_router,
    webhooks as webhooks_router,
    fleet as fleet_router,
    audit as audit_router,
    cron as cron_router,
    databases as databases_router,
    pr_previews as pr_previews_router,
    admin_users as admin_users_router,
    account as account_router,
    resources as resources_router,
    metrics as metrics_router,
    analytics as analytics_router,
    roadmap as roadmap_router,
    status as status_router,
    contact as contact_router,
    tickets as tickets_router,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("deployunit")


scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    connect()
    await ensure_indexes()
    await seed_initial_data()
    await seed_default_plans()
    # One-shot data migration: lift plan + credits + billing profile from
    # workspaces onto their owner user. Skips users already migrated.
    if await needs_migration():
        try:
            result = await migrate_accounts()
            logger.info("account migration: %s", result)
        except Exception as e:
            logger.exception("account migration failed: %s", e)
    scheduler.add_job(run_monitor_tick, "interval", seconds=60, id="monitor", replace_existing=True)
    scheduler.add_job(sync_deployments, "interval", seconds=15, id="deploy_sync", replace_existing=True)
    scheduler.add_job(deployment_watchdog, "interval", seconds=30, id="deploy_watchdog", replace_existing=True, max_instances=2)
    # Credit-wallet monthly grant — runs hourly so anniversary resets are
    # accurate to the hour without spamming the DB.
    scheduler.add_job(monthly_grant_tick, "interval", hours=1, id="credits_grant", replace_existing=True)
    # Per-app resource addon charges — billed on the user's wallet at the
    # 30-day anniversary of when the addon was first activated.
    scheduler.add_job(charge_due_addons, "interval", hours=1, id="resource_billing", replace_existing=True)
    # Periodic status snapshot for the analytics tab (healthy/down timeline).
    scheduler.add_job(status_sampler, "interval", minutes=5, id="status_sampler", replace_existing=True)
    # Container-metrics downsampling: roll raw 30s samples up to 5-min buckets
    # for anything older than 24h, drop anything older than 30 days.
    scheduler.add_job(downsample_and_gc, "interval", hours=1, id="metrics_rollup", replace_existing=True)
    # Daily PageSpeed audits for every app with a primary URL.
    scheduler.add_job(daily_pagespeed_tick, "interval", hours=12, id="pagespeed_daily", replace_existing=True)
    # Analytics retention — drop pageview events older than 90 days.
    scheduler.add_job(analytics_gc, "interval", hours=24, id="analytics_gc", replace_existing=True)
    # Public status page — ping every component every 60 seconds.
    scheduler.add_job(status_ping_tick, "interval", seconds=60, id="status_ping", replace_existing=True)
    # Cloudflare subdomain pool — keep N pre-warmed DNS records so new apps
    # get instantly-resolving URLs at creation time instead of waiting on
    # DNS propagation. Tick every 3 min; refill is a no-op when full.
    scheduler.add_job(subdomain_refill_pool, "interval", minutes=3, id="subdomain_pool_refill", replace_existing=True, max_instances=1)
    # Routing self-healer — probes every live app's Cloudflare FQDN every 2
    # min, auto-pushes the FQDN back to Coolify + restarts the container when
    # Traefik has lost the route ("no available server" / TRAEFIK DEFAULT
    # CERT). Also reaps orphan DNS pool entries whose app no longer exists.
    scheduler.add_job(routing_healer_tick, "interval", minutes=2, id="routing_healer", replace_existing=True, max_instances=1)
    # Coolify ↔ DeployUnit drift reconciler — every 10 min. Archives DeployUnit
    # apps that no longer exist on the build engine and counts Coolify apps
    # not tracked by DeployUnit (info pill only, no warning spam).
    scheduler.add_job(coolify_reconcile_tick, "interval", minutes=10, id="coolify_reconcile", replace_existing=True, max_instances=1)
    # Custom-subdomain verifier — every 30s probes any pending requests
    # and only flips the primary URL to the new subdomain once DNS +
    # Traefik + SSL are all working. Prevents the "user changed name
    # and now their app is unreachable" failure mode.
    scheduler.add_job(verify_pending_subdomains_tick, "interval", seconds=30, id="custom_subdomain_verify", replace_existing=True, max_instances=1)
    # Daily-ish health audit — SSL cert validity + custom-domain registration
    # expiry for every verified custom domain. Per-event dispatcher cooldown
    # prevents repeat pings within 24h for the same problem.
    scheduler.add_job(health_audit_tick, "interval", hours=6, id="health_audit", replace_existing=True, max_instances=1)
    scheduler.start()
    # Initial fill on boot (fire-and-forget) so the very first deploy after
    # a restart doesn't have to wait 3 min for the first scheduler tick.
    import asyncio as _asyncio
    _asyncio.create_task(subdomain_refill_pool())
    logger.info("DeployUnit backend started")
    yield
    scheduler.shutdown(wait=False)
    await disconnect()


app = FastAPI(title="DeployUnit", lifespan=lifespan)

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"service": "deployunit", "status": "ok"}


@api_router.get("/health")
async def health():
    return {"status": "ok"}


api_router.include_router(auth_router.router)
api_router.include_router(github_oauth_router.router)
api_router.include_router(workspaces_router.router)
api_router.include_router(projects_router.router)
api_router.include_router(apps_router.router)
api_router.include_router(deployments_router.router)
api_router.include_router(domains_router.router)
api_router.include_router(monitoring_router.router)
api_router.include_router(alerts_router.router)
api_router.include_router(billing_router.router)
api_router.include_router(notifications_router.router)
api_router.include_router(settings_router.router)
api_router.include_router(github_router.router)
api_router.include_router(admin_router.router)
api_router.include_router(credits_router.router)
api_router.include_router(webhooks_router.router)
api_router.include_router(fleet_router.router)
api_router.include_router(audit_router.router)
api_router.include_router(cron_router.router)
api_router.include_router(databases_router.router)
api_router.include_router(pr_previews_router.router)
api_router.include_router(admin_users_router.router)
api_router.include_router(account_router.router)
api_router.include_router(resources_router.router)
api_router.include_router(metrics_router.router)
api_router.include_router(analytics_router.router)
api_router.include_router(roadmap_router.router)
api_router.include_router(status_router.router)
api_router.include_router(contact_router.router)
api_router.include_router(tickets_router.router)

app.include_router(api_router)

# CORS — explicit origin list for credentialed cookies.
# When CORS_ORIGINS="*" with credentials, browsers reject the wildcard. We
# instead let FastAPI echo the request Origin via allow_origin_regex=".*".
# This is safe because all sensitive endpoints already require JWT + CSRF
# cookies, and it makes preview, production and any custom domain work
# without per-env config.
_origins = os.environ.get("CORS_ORIGINS", "*")
fe = os.environ.get("FRONTEND_URL")
if _origins.strip() == "*":
    cors_kwargs = {"allow_origin_regex": ".*"}
else:
    allow_origins = [o.strip() for o in _origins.split(",") if o.strip()]
    if fe and fe not in allow_origins:
        allow_origins.append(fe)
    cors_kwargs = {"allow_origins": allow_origins}

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    **cors_kwargs,
)
