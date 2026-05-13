"""Environment isolation guard.

DeployUnit runs in two environments that share the SAME external infra
(Coolify, Cloudflare, GitHub, etc.) but must never write each other's
data. This module is the single source of truth for:

  * `is_production()` — am I running on the live deployment?
  * `is_preview()`    — am I running on a preview/dev container?
  * `env_name()`      — short label for logs/tags ("production" | "preview")
  * `require_live_writes(reason)` — raises if called from a non-production
    environment. Use on operations that mutate shared external state.

How env is determined:

  1. Explicit `DEPLOYUNIT_ENV` env var (set to `production` on the live
     deployment via Emergent's deploy panel).
  2. Fallback: inspect `FRONTEND_URL` — if it contains `.preview.` or
     `localhost` it's preview, otherwise production.

  The default is **preview** when nothing is set, so a brand-new pod
  without the env var configured CANNOT accidentally write to live
  Coolify/Cloudflare. Failing safe is the whole point.
"""
from __future__ import annotations

import logging
import os
from typing import Literal

logger = logging.getLogger(__name__)

EnvName = Literal["production", "preview"]


def env_name() -> EnvName:
    explicit = (os.environ.get("DEPLOYUNIT_ENV") or "").strip().lower()
    if explicit in ("production", "prod", "live"):
        return "production"
    if explicit in ("preview", "dev", "development", "staging"):
        return "preview"
    # Fallback heuristic on FRONTEND_URL.
    fe = (os.environ.get("FRONTEND_URL") or os.environ.get("PUBLIC_FRONTEND_URL") or "").lower()
    if ".preview." in fe or "localhost" in fe or "127.0.0.1" in fe:
        return "preview"
    if fe.startswith("https://deployunit.com") or fe.startswith("http://deployunit.com"):
        return "production"
    # Unknown → fail safe to preview (refuses writes).
    return "preview"


def is_production() -> bool:
    return env_name() == "production"


def is_preview() -> bool:
    return env_name() == "preview"


class LiveWriteBlocked(Exception):
    """Raised when preview tries to mutate live infra."""

    def __init__(self, action: str):
        super().__init__(
            f"refusing live-infra write '{action}' from preview environment "
            "(set DEPLOYUNIT_ENV=production to override)"
        )
        self.action = action


def require_live_writes(action: str) -> None:
    """Raise if we're not on production. Callers catch this and treat the
    operation as a no-op (preview should NEVER touch shared external state)."""
    if not is_production():
        raise LiveWriteBlocked(action)


def safe_skip(action: str) -> bool:
    """Returns True if the caller should skip the live-infra mutation.
    Logs the skip on the warning channel so the deploy log surfaces it.

    Use this as a lightweight guard at the top of every mutation method:

        if safe_skip("coolify.deploy"):
            return None
        # ...real call here

    Returns False when env=production so real callers proceed normally.
    """
    if is_production():
        return False
    logger.info("[env-guard] skipping live-infra write '%s' (env=%s)", action, env_name())
    return True
