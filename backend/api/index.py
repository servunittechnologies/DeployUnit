"""Vercel serverless entrypoint for the DeployUnit API (optional).

Deploy the BACKEND as its own Vercel project with Root Directory = `backend`.
Vercel's Python runtime serves this file; the catch-all rewrite in
backend/vercel.json routes every request into the FastAPI app.

IMPORTANT: serverless has no persistent scheduler, so this process runs
web-only (server.py disables the scheduler when VERCEL=1). Run worker.py on an
always-on host or the platform's automation (deploy sync, routing self-healer,
subdomain pool, credit grants, …) will not run. See DEPLOY.md.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app  # noqa: E402  (FastAPI ASGI app)

# Vercel's Python runtime looks for a module-level `app` (ASGI) — re-exported.
__all__ = ["app"]
