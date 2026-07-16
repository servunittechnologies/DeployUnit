"""DeployUnit background worker.

Runs the periodic scheduler jobs (monitoring, deploy sync, routing self-healer,
subdomain pool, credit grants, billing renewals, …) in one always-on process.

Use this when the web app runs somewhere that can't host a persistent scheduler
— e.g. the web tier is on Vercel serverless (VERCEL=1 disables the in-app
scheduler) or you simply want web and worker scaled separately. Run exactly ONE
worker against a given database.

    python worker.py

Reads the same .env / environment as the web app (MONGO_URL, DB_NAME, COOLIFY_*,
CLOUDFLARE via platform_settings, etc.).
"""

import asyncio
import logging

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402

from db import connect, disconnect  # noqa: E402
from server import register_jobs, run_startup_maintenance  # noqa: E402
from services.subdomains import refill_pool as subdomain_refill_pool  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("deployunit.worker")


async def main():
    connect()
    await run_startup_maintenance()
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler)
    scheduler.start()
    # Warm the subdomain pool immediately so the first deploy doesn't wait.
    asyncio.create_task(subdomain_refill_pool())
    logger.info("DeployUnit worker started — %d jobs scheduled", len(scheduler.get_jobs()))
    try:
        # Block forever; the scheduler runs on this event loop.
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        await disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("DeployUnit worker stopped")
