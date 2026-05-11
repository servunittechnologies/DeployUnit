"""Metrics ingest service — receives docker-stats samples from the metrics
agent running on the build engine VPS, normalises them and persists to
`container_metrics_samples`. Provides aggregation helpers for the analytics
endpoints.

Storage design
--------------
We keep RAW samples (every 30s by default) for 24 hours, then automatically
DOWNSAMPLE to 5-min buckets for 30 days. Drops anything older. This keeps
the collection small and queries fast.

Auth
----
The agent posts with header `X-Agent-Key: <token>`. The shared key is stored
hashed in `platform_settings.agent_api_key_hash` and shown to the admin ONCE
when generated/rotated.
"""
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import get_db

logger = logging.getLogger(__name__)

PLATFORM_SETTINGS_ID = "platform-singleton"

RAW_RETENTION = timedelta(hours=24)
ROLLUP_RETENTION = timedelta(days=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ─────────────────────── Agent key management ───────────────────────
async def get_or_create_agent_key_info() -> dict:
    """Returns presence info (without exposing the actual key)."""
    db = get_db()
    doc = await db.platform_settings.find_one({"id": PLATFORM_SETTINGS_ID}, {"_id": 0}) or {}
    agent = doc.get("metrics_agent") or {}
    return {
        "configured": bool(agent.get("api_key_hash")),
        "created_at": agent.get("created_at"),
        "last_seen_at": agent.get("last_seen_at"),
        "last_sample_count": agent.get("last_sample_count"),
    }


async def rotate_agent_key() -> str:
    """Generate a fresh agent key, store its hash, return the cleartext ONCE."""
    db = get_db()
    key = "dh-agent-" + secrets.token_urlsafe(40)
    await db.platform_settings.update_one(
        {"id": PLATFORM_SETTINGS_ID},
        {"$set": {
            "metrics_agent.api_key_hash": _hash(key),
            "metrics_agent.created_at": _now().isoformat(),
        },
         "$setOnInsert": {"id": PLATFORM_SETTINGS_ID}},
        upsert=True,
    )
    return key


async def verify_agent_key(provided: str) -> bool:
    if not provided:
        return False
    db = get_db()
    doc = await db.platform_settings.find_one({"id": PLATFORM_SETTINGS_ID}, {"_id": 0, "metrics_agent": 1}) or {}
    expected = (doc.get("metrics_agent") or {}).get("api_key_hash")
    if not expected:
        return False
    return secrets.compare_digest(expected, _hash(provided))


# ─────────────────────── Sample ingestion ───────────────────────
async def ingest_samples(samples: list[dict], *, source_ip: Optional[str] = None) -> dict:
    """Persist a batch of agent samples. Each sample is matched to an app via
    `coolify_app_uuid` so we only store stats for apps DeployHub knows about.

    Returns counts so the agent can log success/skip rates.
    """
    db = get_db()
    if not samples:
        return {"accepted": 0, "skipped": 0}

    # Bulk lookup of apps by their coolify_app_uuid — and also resolve
    # database-container UUIDs so the agent's DB samples don't get skipped.
    uuids = list({s.get("coolify_app_uuid") for s in samples if s.get("coolify_app_uuid")})
    apps: dict[str, dict] = {}
    if uuids:
        cur = db.apps.find({"coolify_app_uuid": {"$in": uuids}}, {"_id": 0, "id": 1, "workspace_id": 1, "coolify_app_uuid": 1})
        async for a in cur:
            apps[a["coolify_app_uuid"]] = a
        cur2 = db.databases.find({"coolify_app_uuid": {"$in": uuids}}, {"_id": 0, "id": 1, "workspace_id": 1, "coolify_app_uuid": 1})
        async for d in cur2:
            # Store under same dict — DB samples land in container_metrics_samples
            # with `app_id` pointing at the database's id; the analytics layer
            # treats them as their own resource type.
            apps.setdefault(d["coolify_app_uuid"], {
                "id": d["id"], "workspace_id": d["workspace_id"],
                "coolify_app_uuid": d["coolify_app_uuid"], "_kind": "database",
            })

    now_iso = _now().isoformat()
    accepted = 0
    skipped = 0
    docs: list[dict] = []
    for s in samples:
        app = apps.get(s.get("coolify_app_uuid"))
        if not app:
            skipped += 1
            continue
        docs.append({
            "id": str(uuid.uuid4()),
            "app_id": app["id"],
            "workspace_id": app["workspace_id"],
            "coolify_app_uuid": s.get("coolify_app_uuid"),
            "container_id": s.get("container_id"),
            "container_name": s.get("container_name"),
            "sampled_at": s.get("sampled_at") or now_iso,
            "cpu_pct": float(s.get("cpu_pct") or 0),
            "mem_used_mb": int(s.get("mem_used_mb") or 0),
            "mem_limit_mb": int(s.get("mem_limit_mb") or 0),
            "mem_pct": float(s.get("mem_pct") or 0),
            "net_rx_bytes": int(s.get("net_rx_bytes") or 0),
            "net_tx_bytes": int(s.get("net_tx_bytes") or 0),
            "disk_read_bytes": int(s.get("disk_read_bytes") or 0),
            "disk_write_bytes": int(s.get("disk_write_bytes") or 0),
            "disk_used_mb": int(s.get("disk_used_mb") or 0),
        })
        accepted += 1
    if docs:
        await db.container_metrics_samples.insert_many(docs)
    # Update last_seen on the agent record
    await db.platform_settings.update_one(
        {"id": PLATFORM_SETTINGS_ID},
        {"$set": {
            "metrics_agent.last_seen_at": now_iso,
            "metrics_agent.last_sample_count": accepted,
            "metrics_agent.last_source_ip": source_ip,
        }},
        upsert=True,
    )
    return {"accepted": accepted, "skipped": skipped}


# ─────────────────────── Retention / downsampling ───────────────────────
async def downsample_and_gc() -> dict:
    """Hourly job: collapse 30s-raw → 5-min buckets for anything older than
    24h, drop anything older than 30 days.

    The downsampled rows live in the same collection but carry a `rollup=5m`
    marker; raw samples are `rollup=raw` (default if missing)."""
    db = get_db()
    now = _now()
    raw_cut = (now - RAW_RETENTION).isoformat()
    drop_cut = (now - ROLLUP_RETENTION).isoformat()

    # 1) Drop ancient rollups
    drop = await db.container_metrics_samples.delete_many({"sampled_at": {"$lt": drop_cut}})

    # 2) Pull RAW samples older than 24h, downsample to 5-min bucketed averages
    cur = db.container_metrics_samples.aggregate([
        {"$match": {"sampled_at": {"$lt": raw_cut}, "rollup": {"$ne": "5m"}}},
        {"$addFields": {
            "_ts": {"$dateFromString": {"dateString": "$sampled_at"}},
        }},
        {"$group": {
            "_id": {
                "app_id": "$app_id",
                "bucket": {"$dateTrunc": {"date": "$_ts", "unit": "minute", "binSize": 5}},
            },
            "cpu_pct":          {"$avg": "$cpu_pct"},
            "mem_used_mb":      {"$avg": "$mem_used_mb"},
            "mem_limit_mb":     {"$max": "$mem_limit_mb"},
            "mem_pct":          {"$avg": "$mem_pct"},
            "net_rx_bytes":     {"$max": "$net_rx_bytes"},
            "net_tx_bytes":     {"$max": "$net_tx_bytes"},
            "disk_read_bytes":  {"$max": "$disk_read_bytes"},
            "disk_write_bytes": {"$max": "$disk_write_bytes"},
            "disk_used_mb":     {"$max": "$disk_used_mb"},
            "workspace_id":     {"$first": "$workspace_id"},
            "coolify_app_uuid": {"$first": "$coolify_app_uuid"},
            "container_name":   {"$first": "$container_name"},
            "n":                {"$sum": 1},
        }},
    ])
    bucketed = []
    async for r in cur:
        bucketed.append({
            "id": str(uuid.uuid4()),
            "app_id": r["_id"]["app_id"],
            "workspace_id": r.get("workspace_id"),
            "coolify_app_uuid": r.get("coolify_app_uuid"),
            "container_name": r.get("container_name"),
            "sampled_at": r["_id"]["bucket"].isoformat(),
            "cpu_pct": round(r["cpu_pct"] or 0, 2),
            "mem_used_mb": int(r["mem_used_mb"] or 0),
            "mem_limit_mb": int(r["mem_limit_mb"] or 0),
            "mem_pct": round(r["mem_pct"] or 0, 2),
            "net_rx_bytes": int(r["net_rx_bytes"] or 0),
            "net_tx_bytes": int(r["net_tx_bytes"] or 0),
            "disk_read_bytes": int(r["disk_read_bytes"] or 0),
            "disk_write_bytes": int(r["disk_write_bytes"] or 0),
            "disk_used_mb": int(r["disk_used_mb"] or 0),
            "rollup": "5m",
            "n_samples": r["n"],
        })
    if bucketed:
        await db.container_metrics_samples.insert_many(bucketed)
        # Now drop the original raw rows we just rolled-up
        await db.container_metrics_samples.delete_many({
            "sampled_at": {"$lt": raw_cut}, "rollup": {"$ne": "5m"}
        })
    return {
        "ran_at": now.isoformat(),
        "dropped_old": drop.deleted_count,
        "rolled_up": len(bucketed),
    }


# ─────────────────────── Query helpers ───────────────────────
async def app_metrics_series(app_id: str, *, window: str = "24h", limit: int = 500) -> dict:
    """Return ordered time-series of metric samples for one app over the
    requested window. The frontend can plot these directly."""
    db = get_db()
    deltas = {
        "1h":  timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d":  timedelta(days=7),
        "30d": timedelta(days=30),
    }
    delta = deltas.get(window, deltas["24h"])
    since = (_now() - delta).isoformat()
    rows = await db.container_metrics_samples.find(
        {"app_id": app_id, "sampled_at": {"$gte": since}},
        {"_id": 0, "sampled_at": 1, "cpu_pct": 1, "mem_used_mb": 1, "mem_limit_mb": 1,
         "mem_pct": 1, "net_rx_bytes": 1, "net_tx_bytes": 1,
         "disk_read_bytes": 1, "disk_write_bytes": 1, "disk_used_mb": 1, "rollup": 1},
    ).sort("sampled_at", 1).limit(limit).to_list(limit)
    return {
        "window": window,
        "since": since,
        "samples": rows,
        "latest": rows[-1] if rows else None,
        "have_data": len(rows) > 0,
    }
