"""Vercel serverless entrypoint for the DeployUnit API (single-project deploy).

The whole repo deploys as ONE Vercel project: the React frontend as static
output and this file as a Python serverless function serving the FastAPI app.
vercel.json routes /api/* here; everything else falls through to the SPA.

The backend package lives in ../backend and is bundled via `includeFiles` in
vercel.json. Vercel injects VERCEL=1, so server.py runs web-only (the
in-process scheduler is off) — the periodic jobs run via Vercel Cron hitting
/api/cron/* (also configured in vercel.json). See DEPLOY.md.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from server import app  # noqa: E402  (FastAPI ASGI app)

__all__ = ["app"]
