"""Usage analytics — aggregates the signals we can actually measure into a
single payload that the UI can plot:

  * Uptime % over the window               (from monitoring_results)
  * Response time time-series               (from monitoring_results)
  * Status timeline (live / down / building) — derived from app_status_samples
  * Build minutes consumed in the window    (from deployments)
  * Credit consumption time-series          (from credit_transactions)
  * Resources currently allocated           (from app.resources_addons + plan)

Coolify v4 does NOT expose per-container CPU/memory %, so we don't fake
those numbers — instead we surface the LIMIT the container is running with
and the HEALTH status that drives whether it's actively running or not.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import get_db
from services.resources import resolve_app_resources

logger = logging.getLogger(__name__)

WINDOWS = {
    "1h":  timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d":  timedelta(days=7),
    "30d": timedelta(days=30),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _bucket_for_window(window: str) -> timedelta:
    """How big each chart bucket should be for nice ~60-point series."""
    return {
        "1h":  timedelta(minutes=1),
        "24h": timedelta(minutes=20),
        "7d":  timedelta(hours=2),
        "30d": timedelta(hours=8),
    }.get(window, timedelta(hours=1))


def _floor_to_bucket(ts: datetime, size: timedelta) -> datetime:
    sec = size.total_seconds()
    epoch = int(ts.timestamp() // sec * sec)
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


# ─────────────────────── App analytics ───────────────────────
async def app_analytics(app_id: str, window: str = "24h") -> dict:
    db = get_db()
    delta = WINDOWS.get(window, WINDOWS["24h"])
    since = _now() - delta
    bucket = _bucket_for_window(window)

    app = await db.apps.find_one({"id": app_id}, {"_id": 0})
    if not app:
        return {}

    # 1) Monitoring results → uptime + response time
    rows = await db.monitoring_results.find(
        {"app_id": app_id, "timestamp": {"$gte": since.isoformat()}},
        {"_id": 0, "timestamp": 1, "ok": 1, "response_time_ms": 1, "status_code": 1},
    ).sort("timestamp", 1).to_list(5000)
    samples_count = len(rows)
    ok_count = sum(1 for r in rows if r.get("ok"))
    uptime_pct = round(100 * ok_count / samples_count, 2) if samples_count else None
    rt_values = [r["response_time_ms"] for r in rows if r.get("response_time_ms") is not None]
    avg_response_ms = round(sum(rt_values) / len(rt_values)) if rt_values else None
    p95_response_ms = _percentile(rt_values, 95) if rt_values else None

    # 2) Response-time + availability time-series (bucketed)
    buckets: dict[datetime, dict] = {}
    for r in rows:
        try:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
        except Exception:
            continue
        key = _floor_to_bucket(ts, bucket)
        b = buckets.setdefault(key, {"ok": 0, "fail": 0, "rt_sum": 0, "rt_n": 0})
        if r.get("ok"):
            b["ok"] += 1
        else:
            b["fail"] += 1
        if r.get("response_time_ms") is not None:
            b["rt_sum"] += r["response_time_ms"]
            b["rt_n"] += 1
    series_uptime = []
    series_response = []
    for k in sorted(buckets.keys()):
        b = buckets[k]
        total = b["ok"] + b["fail"]
        series_uptime.append({
            "t": k.isoformat(),
            "uptime_pct": round(100 * b["ok"] / total, 2) if total else None,
            "samples": total,
        })
        series_response.append({
            "t": k.isoformat(),
            "avg_ms": round(b["rt_sum"] / b["rt_n"]) if b["rt_n"] else None,
        })

    # 3) Deployments + build minutes
    deps = await db.deployments.find(
        {"app_id": app_id, "started_at": {"$gte": since.isoformat()}},
        {"_id": 0, "id": 1, "status": 1, "started_at": 1, "finished_at": 1, "trigger": 1},
    ).sort("started_at", 1).to_list(500)
    build_seconds_total = 0
    deploys_by_status = {"live": 0, "failed": 0, "canceled": 0, "building": 0, "queued": 0}
    for d in deps:
        deploys_by_status[d.get("status", "?")] = deploys_by_status.get(d.get("status", "?"), 0) + 1
        if d.get("started_at") and d.get("finished_at"):
            try:
                s = datetime.fromisoformat(d["started_at"].replace("Z", "+00:00"))
                f = datetime.fromisoformat(d["finished_at"].replace("Z", "+00:00"))
                build_seconds_total += max(0, (f - s).total_seconds())
            except Exception:
                pass
    build_minutes = round(build_seconds_total / 60.0, 1)

    # 4) Currently allocated resources (and addons)
    resources = await resolve_app_resources(app)

    # 5) Status timeline — collapse consecutive identical statuses
    timeline_raw = await db.app_status_samples.find(
        {"app_id": app_id, "sampled_at": {"$gte": since.isoformat()}},
        {"_id": 0, "status": 1, "sampled_at": 1},
    ).sort("sampled_at", 1).to_list(2000)
    timeline = _collapse_timeline(timeline_raw, since=since, now=_now())

    return {
        "app_id": app_id,
        "name": app.get("name"),
        "window": window,
        "since": since.isoformat(),
        "now": _now().isoformat(),
        "status": app.get("status"),
        "primary_url": app.get("primary_url"),
        "summary": {
            "uptime_pct": uptime_pct,
            "avg_response_ms": avg_response_ms,
            "p95_response_ms": p95_response_ms,
            "samples": samples_count,
            "deployments": len(deps),
            "deploys_by_status": deploys_by_status,
            "build_minutes": build_minutes,
        },
        "resources": resources,
        "series": {
            "uptime": series_uptime,
            "response_ms": series_response,
        },
        "status_timeline": timeline,
        "deployments_recent": deps[-10:],
    }


def _percentile(values: list[float], pct: float) -> Optional[int]:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return int(s[f])
    return int(s[f] + (s[c] - s[f]) * (k - f))


def _collapse_timeline(raw: list[dict], *, since: datetime, now: datetime) -> list[dict]:
    """Group consecutive samples with the same status into ranges."""
    if not raw:
        return []
    out = []
    cur_status = None
    cur_start = None
    for s in raw:
        try:
            ts = datetime.fromisoformat(s["sampled_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        status = s.get("status") or "?"
        if status != cur_status:
            if cur_status is not None:
                out.append({"status": cur_status, "from": cur_start.isoformat(), "to": ts.isoformat()})
            cur_status = status
            cur_start = ts
    if cur_status:
        out.append({"status": cur_status, "from": cur_start.isoformat(),
                    "to": now.isoformat()})
    return out


# ─────────────────────── Account-wide rollup ───────────────────────
async def account_analytics(user_id: str, window: str = "30d") -> dict:
    """Roll-up analytics across every workspace the user owns:
      * total apps + live count
      * total allocated resources (sum of effective cpu/mem/storage)
      * build minutes in window
      * credit consumption in window (broken out by reason)
      * resource cost forecast (sum of monthly_resource_cost across apps)
    """
    db = get_db()
    delta = WINDOWS.get(window, WINDOWS["30d"])
    since = _now() - delta
    bucket = _bucket_for_window(window)

    ws_ids = await db.workspaces.distinct("id", {"owner_id": user_id})
    if not ws_ids:
        return {"apps_total": 0, "apps_live": 0, "window": window}
    apps = await db.apps.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0}).to_list(500)

    total_cpu = 0.0
    total_mem = 0
    total_storage = 0
    total_monthly_cost = 0
    live_count = 0
    per_app = []
    for a in apps:
        if a.get("status") == "live":
            live_count += 1
        res = await resolve_app_resources(a)
        eff = res["effective"]
        total_cpu += float(eff["cpu_vcpu"])
        total_mem += int(eff["memory_mb"])
        total_storage += int(eff["storage_mb"])
        total_monthly_cost += int(res.get("monthly_cost_credits") or 0)
        per_app.append({
            "app_id": a["id"], "name": a["name"], "status": a.get("status"),
            "workspace_id": a["workspace_id"],
            "effective": eff,
            "monthly_cost_credits": res.get("monthly_cost_credits") or 0,
        })

    # Build minutes for ALL apps in the window
    apps_ids = [a["id"] for a in apps]
    deps = await db.deployments.find(
        {"app_id": {"$in": apps_ids}, "started_at": {"$gte": since.isoformat()}},
        {"_id": 0, "started_at": 1, "finished_at": 1, "status": 1},
    ).to_list(2000) if apps_ids else []
    build_seconds = 0
    for d in deps:
        if d.get("started_at") and d.get("finished_at"):
            try:
                s = datetime.fromisoformat(d["started_at"].replace("Z", "+00:00"))
                f = datetime.fromisoformat(d["finished_at"].replace("Z", "+00:00"))
                build_seconds += max(0, (f - s).total_seconds())
            except Exception:
                pass

    # Credit consumption broken down by reason kind
    txns = await db.credit_transactions.find(
        {"user_id": user_id, "created_at": {"$gte": since.isoformat()}},
        {"_id": 0, "type": 1, "amount": 1, "reason": 1, "created_at": 1, "ref_type": 1},
    ).sort("created_at", 1).to_list(5000)
    burn_by_kind: dict[str, int] = {}
    burn_series: dict[datetime, int] = {}
    grant_series: dict[datetime, int] = {}
    for t in txns:
        try:
            ts = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        key = _floor_to_bucket(ts, bucket)
        amt = int(t.get("amount") or 0)
        if t.get("type") == "consume":
            kind = t.get("ref_type") or "other"
            burn_by_kind[kind] = burn_by_kind.get(kind, 0) + amt
            burn_series[key] = burn_series.get(key, 0) + amt
        elif t.get("type") in ("topup", "grant", "refund", "admin"):
            grant_series[key] = grant_series.get(key, 0) + amt
    series = []
    keys = sorted(set(list(burn_series.keys()) + list(grant_series.keys())))
    cum = 0
    for k in keys:
        burn = burn_series.get(k, 0)
        grant = grant_series.get(k, 0)
        cum += grant - burn
        series.append({"t": k.isoformat(), "burn": burn, "grant": grant, "net_balance_change": grant - burn})

    return {
        "window": window,
        "since": since.isoformat(),
        "now": _now().isoformat(),
        "totals": {
            "workspaces": len(ws_ids),
            "apps_total": len(apps),
            "apps_live": live_count,
            "cpu_allocated_vcpu": round(total_cpu, 2),
            "memory_allocated_mb": total_mem,
            "storage_allocated_mb": total_storage,
            "monthly_resource_cost_credits": total_monthly_cost,
            "build_minutes_in_window": round(build_seconds / 60.0, 1),
            "deployments_in_window": len(deps),
        },
        "credits": {
            "burn_total": sum(burn_by_kind.values()),
            "burn_by_kind": burn_by_kind,
            "series": series,
        },
        "per_app": sorted(per_app, key=lambda x: -x["monthly_cost_credits"])[:25],
    }
