"""DeployHub API entrypoint."""
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
from workers.monitor import run_monitor_tick, sync_deployments, deployment_watchdog

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
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("deployhub")


scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    connect()
    await ensure_indexes()
    await seed_initial_data()
    scheduler.add_job(run_monitor_tick, "interval", seconds=60, id="monitor", replace_existing=True)
    scheduler.add_job(sync_deployments, "interval", seconds=15, id="deploy_sync", replace_existing=True)
    scheduler.add_job(deployment_watchdog, "interval", seconds=30, id="deploy_watchdog", replace_existing=True)
    scheduler.start()
    logger.info("DeployHub backend started")
    yield
    scheduler.shutdown(wait=False)
    await disconnect()


app = FastAPI(title="DeployHub", lifespan=lifespan)

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"service": "deployhub", "status": "ok"}


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

app.include_router(api_router)

# CORS — explicit origin list for credentialed cookies.
_origins = os.environ.get("CORS_ORIGINS", "*")
if _origins.strip() == "*":
    allow_origins = [os.environ.get("FRONTEND_URL", "http://localhost:3000")]
else:
    allow_origins = [o.strip() for o in _origins.split(",") if o.strip()]
# Always also include configured FRONTEND_URL
fe = os.environ.get("FRONTEND_URL")
if fe and fe not in allow_origins:
    allow_origins.append(fe)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
