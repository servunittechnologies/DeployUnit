"""Metrics ingestion + agent installer routes.

* `POST /api/metrics/ingest`           — agent posts samples (X-Agent-Key auth)
* `GET  /api/admin/metrics/agent`      — admin: agent status + install snippet
* `POST /api/admin/metrics/agent/rotate` — admin: rotate API key
* `GET  /api/agent/install.sh`         — public: bash installer (interactive)
* `GET  /api/agent/agent.py`           — public: Python agent script (pulled by the installer)
* `GET  /api/apps/{id}/metrics`        — workspace member: query app metrics time-series
"""
import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from services.metrics import (
    ingest_samples, verify_agent_key, rotate_agent_key,
    get_or_create_agent_key_info, app_metrics_series,
)
from services.audit import log as audit_log

logger = logging.getLogger(__name__)
router = APIRouter(tags=["metrics"])


# ─────────────────────── Ingest ───────────────────────
class IngestBody(BaseModel):
    samples: list[dict]


@router.post("/metrics/ingest")
async def post_ingest(payload: IngestBody, request: Request,
                      x_agent_key: Optional[str] = Header(default=None)):
    if not await verify_agent_key(x_agent_key or ""):
        raise HTTPException(status_code=401, detail="invalid agent key")
    source_ip = request.client.host if request.client else None
    res = await ingest_samples(payload.samples, source_ip=source_ip)
    return res


# ─────────────────────── Admin ───────────────────────
async def _require_admin(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    return user


import os


def _public_base(request: Request) -> str:
    """Use FRONTEND_URL (user's external HTTPS URL) for the install command
    and agent endpoint, falling back to request.base_url for dev environments."""
    env = (os.environ.get("FRONTEND_URL") or "").rstrip("/")
    if env:
        return env
    return str(request.base_url).rstrip("/")


@router.get("/admin/metrics/agent")
async def admin_agent_status(request: Request):
    await _require_admin(request)
    info = await get_or_create_agent_key_info()
    api_base = _public_base(request)
    return {
        **info,
        "install_command": f"curl -sSL {api_base}/api/agent/install.sh | bash",
        "manual_endpoint": f"{api_base}/api/metrics/ingest",
    }


@router.post("/admin/metrics/agent/rotate")
async def admin_rotate_agent_key(request: Request):
    user = await _require_admin(request)
    key = await rotate_agent_key()
    audit_log(action="admin.metrics_agent_key_rotate", actor=user,
              resource_type="platform", resource_id="agent_key",
              meta={}, request=request)
    return {"api_key": key,
            "warning": "store this NOW — we only show it once and it can't be retrieved."}


# ─────────────────────── Public installer (no auth) ───────────────────────
@router.get("/agent/install.sh")
async def agent_installer(request: Request):
    """Bash one-liner: `curl -sSL <host>/api/agent/install.sh | bash`.

    Prompts the operator interactively for the API key (because we don't
    bake it into the public response), then deploys a docker-compose
    container that runs the metrics agent.
    """
    api_base = _public_base(request)
    script = AGENT_INSTALL_SH.format(api_base=api_base)
    return PlainTextResponse(script, media_type="text/x-shellscript")


@router.get("/agent/agent.py")
async def agent_script():
    """Python source the installed docker-compose service runs. Served as
    plain text so the installer can `curl` it directly."""
    return PlainTextResponse(AGENT_PY, media_type="text/x-python")


# ─────────────────────── App-side query ───────────────────────
@router.get("/apps/{app_id}/metrics")
async def app_metrics(app_id: str, request: Request, window: str = "24h"):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id}, {"_id": 0, "workspace_id": 1})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    return await app_metrics_series(app_id, window=window)


# ===================================================================
# Inline installer + agent — kept here so we can ship via plain HTTP
# ===================================================================
AGENT_INSTALL_SH = r"""#!/usr/bin/env bash
# DeployUnit metrics agent installer — run on your build engine VPS.
# It deploys a tiny container that POSTs `docker stats` to DeployUnit every 30s.
set -e

API_BASE="{api_base}"
INSTALL_DIR="/opt/deployunit-agent"

echo ""
echo "DeployUnit metrics agent installer"
echo "================================="
echo "  target server: $API_BASE"
echo ""

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed on this host." >&2
  exit 1
fi

# When run as `curl ... | bash`, stdin is the script itself — we need to
# explicitly read from the terminal device for an interactive prompt.
# DH_AGENT_KEY env var also works (skips the prompt).
if [ -z "${{DH_AGENT_KEY:-}}" ]; then
  if [ ! -t 0 ] && [ ! -r /dev/tty ]; then
    echo "ERROR: no TTY for prompt. Pass the key as env:" >&2
    echo "  curl -sSL $API_BASE/api/agent/install.sh | DH_AGENT_KEY=dh-agent-xxxx bash" >&2
    exit 1
  fi
  echo "Paste your DeployUnit agent API key (input hidden). Get it in Admin → Integrations → Metrics agent."
  read -r -s -p "key: " DH_AGENT_KEY < /dev/tty
  echo ""
fi
if [ -z "${{DH_AGENT_KEY}}" ]; then
  echo "ERROR: empty key" >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Pull the agent script
curl -sSL "$API_BASE/api/agent/agent.py" -o agent.py
if [ ! -s agent.py ]; then
  echo "ERROR: could not download agent.py from $API_BASE" >&2
  exit 1
fi

# Write the docker-compose file (variables resolved to plain strings so
# this works on any docker compose version, with or without env-file).
cat > docker-compose.yml <<DCYAML
services:
  agent:
    image: python:3.11-slim
    container_name: deployunit-metrics-agent
    restart: unless-stopped
    pid: "host"
    network_mode: "host"
    environment:
      DH_API_URL: "$API_BASE"
      DH_AGENT_KEY: "$DH_AGENT_KEY"
      INTERVAL_SEC: "30"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./agent.py:/agent.py:ro
    command: ["bash","-lc","pip install --quiet 'httpx<1' 'docker<8' && exec python -u /agent.py"]
DCYAML

# Stop any previous version cleanly
docker rm -f deployunit-metrics-agent >/dev/null 2>&1 || true
docker compose up -d

echo ""
echo "Done. DeployUnit agent running."
echo "  watch logs:  docker logs -f deployunit-metrics-agent"
echo "  reinstall:   curl -sSL $API_BASE/api/agent/install.sh | bash"
echo "  uninstall:   docker rm -f deployunit-metrics-agent && rm -rf $INSTALL_DIR"
echo ""
"""


AGENT_PY = r'''"""DeployUnit metrics agent — runs inside `python:3.11-slim` next to Docker
on the build engine VPS. Loops every $INTERVAL_SEC, posts a JSON batch to
DeployUnit. Lean by design (one file, two deps)."""
import os
import re
import sys
import time
import logging
from datetime import datetime, timezone

import docker
import httpx

API_URL = os.environ.get("DH_API_URL", "").rstrip("/")
API_KEY = os.environ.get("DH_AGENT_KEY", "")
INTERVAL = int(os.environ.get("INTERVAL_SEC") or 30)

logging.basicConfig(level=logging.INFO, format="%(asctime)s agent: %(message)s")
log = logging.getLogger("dh-agent")

if not API_URL or not API_KEY:
    log.error("missing DH_API_URL or DH_AGENT_KEY env vars")
    sys.exit(2)

client = docker.from_env()


# Coolify container names look like:
#   <uuid>                       — for plain databases/services (older revs)
#   <uuid>-<random_suffix>       — for application revisions, suffix can be
#                                  digits OR alphanumeric depending on the
#                                  Coolify version
# The `coolify.applicationId` label is the integer Laravel DB id, NOT the
# UUID we use in DeployUnit, so we ALSO try several UUID-bearing labels
# before falling back to a name-prefix regex.
NAME_RE = re.compile(r"^([a-z0-9]{20,32})(?:-[a-z0-9]+)?$")

UUID_LABELS = [
    "coolify.applicationUUID",
    "coolify.application.uuid",
    "coolify.databaseUUID",
    "coolify.database.uuid",
    "coolify.serviceUUID",
    "coolify.service.uuid",
    "coolify.resource.uuid",
    "coolify.resourceUUID",
    "coolify.uuid",
]


def _resource_uuid_from(c) -> str | None:
    labels = c.labels or {}
    for k in UUID_LABELS:
        v = labels.get(k)
        if v and isinstance(v, str) and 8 <= len(v) <= 64:
            return v
    name = (c.name or "").lstrip("/")
    m = NAME_RE.match(name)
    if m:
        return m.group(1)
    return None


# Internal Coolify infra containers we always want to ignore.
INFRA_PREFIXES = (
    "coolify-proxy", "coolify-realtime", "coolify-db", "coolify-redis",
    "coolify-helper", "coolify-mailpit", "coolify-",
)


def _is_coolify_app(c) -> bool:
    labels = c.labels or {}
    name = (c.name or "").lstrip("/")
    if any(name.startswith(p) for p in INFRA_PREFIXES):
        return False
    if labels.get("coolify.managed") != "true":
        return False
    return _resource_uuid_from(c) is not None


def _cpu_pct(stats: dict) -> float:
    try:
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"].get("total_usage", 0)
        sys_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"].get("system_cpu_usage", 0)
        online = stats["cpu_stats"].get("online_cpus") or 1
        if sys_delta > 0 and cpu_delta > 0:
            return round((cpu_delta / sys_delta) * online * 100.0, 2)
    except Exception:
        pass
    return 0.0


def _mem(stats: dict):
    m = stats.get("memory_stats", {}) or {}
    used = int(m.get("usage") or 0)
    cache = ((m.get("stats") or {}).get("inactive_file") or 0) or ((m.get("stats") or {}).get("cache") or 0)
    used = max(0, used - cache)
    limit = int(m.get("limit") or 0)
    pct = round((used / limit) * 100.0, 2) if limit else 0.0
    return used // (1024 * 1024), limit // (1024 * 1024), pct


def _net(stats: dict):
    rx, tx = 0, 0
    for iface in (stats.get("networks") or {}).values():
        rx += int(iface.get("rx_bytes") or 0)
        tx += int(iface.get("tx_bytes") or 0)
    return rx, tx


def _disk_io(stats: dict):
    r, w = 0, 0
    blkio = (stats.get("blkio_stats") or {}).get("io_service_bytes_recursive") or []
    for entry in blkio:
        op = (entry.get("op") or "").lower()
        if op == "read":
            r += int(entry.get("value") or 0)
        elif op == "write":
            w += int(entry.get("value") or 0)
    return r, w


def collect_samples() -> list[dict]:
    out: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    try:
        containers = client.containers.list()
    except Exception as e:
        log.error("list containers: %s", e)
        return out
    seen_managed = 0
    skipped_no_uuid: list[str] = []
    for c in containers:
        labels = c.labels or {}
        if labels.get("coolify.managed") != "true":
            continue
        seen_managed += 1
        if not _is_coolify_app(c):
            skipped_no_uuid.append(c.name or "?")
            continue
        coolify_uuid = _resource_uuid_from(c)
        try:
            stats = c.stats(stream=False)
        except Exception as e:
            log.warning("stats %s: %s", c.name, e)
            continue
        mem_used, mem_limit, mem_pct = _mem(stats)
        net_rx, net_tx = _net(stats)
        disk_r, disk_w = _disk_io(stats)
        out.append({
            "container_id": (c.id or "")[:12],
            "container_name": c.name,
            "coolify_app_uuid": coolify_uuid,
            "sampled_at": now,
            "cpu_pct": _cpu_pct(stats),
            "mem_used_mb": mem_used,
            "mem_limit_mb": mem_limit,
            "mem_pct": mem_pct,
            "net_rx_bytes": net_rx,
            "net_tx_bytes": net_tx,
            "disk_read_bytes": disk_r,
            "disk_write_bytes": disk_w,
        })
    log.info(
        "tick: managed=%d sampled=%d skipped_no_uuid=%d %s",
        seen_managed, len(out), len(skipped_no_uuid),
        ("(skipped: " + ", ".join(skipped_no_uuid[:5]) + ")") if skipped_no_uuid else "",
    )
    for s in out:
        log.info("  -> %s  uuid=%s  cpu=%.1f%%  mem=%.1f%%",
                 s["container_name"], s["coolify_app_uuid"], s["cpu_pct"], s["mem_pct"])
    return out


def push(samples: list[dict]) -> None:
    # Always ping so the admin can tell the agent is alive even if no
    # Coolify-managed apps were detected this tick.
    if not samples:
        log.info("no Coolify-managed app containers found this tick (heartbeat only)")
    try:
        r = httpx.post(
            f"{API_URL}/api/metrics/ingest",
            json={"samples": samples},
            headers={"X-Agent-Key": API_KEY},
            timeout=15.0,
        )
        if r.status_code >= 300:
            log.error("push HTTP %s: %s", r.status_code, r.text[:200])
        else:
            try:
                resp = r.json()
                log.info("pushed %d samples (accepted=%d, skipped=%d) unmapped=%s",
                         len(samples), resp.get("accepted", 0), resp.get("skipped", 0),
                         resp.get("unmapped_uuids", []))
            except Exception:
                log.info("pushed %d samples", len(samples))
    except Exception as e:
        log.error("push: %s", e)


def main() -> None:
    log.info("DeployUnit agent starting endpoint=%s interval=%ss", API_URL, INTERVAL)
    while True:
        t0 = time.time()
        push(collect_samples())
        elapsed = time.time() - t0
        time.sleep(max(1.0, INTERVAL - elapsed))


if __name__ == "__main__":
    main()
'''
