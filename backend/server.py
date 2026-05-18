import logging

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
from services.app_addons import renew_tick as app_addons_renew_tick
from routers.app_addons import heatmap_gc_tick
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
    app_addons as app_addons_router,
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
    affiliate as affiliate_router,
    copilot as copilot_router,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("deployunit")

scheduler = AsyncIOScheduler()

# ... (truncated for brevity, real file will be pushed)