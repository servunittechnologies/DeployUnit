"""Plan service — single source of truth for subscription plans.

Plans live in MongoDB (collection `platform_plans`) so admins can tweak
prices, limits, and features without redeploys. On first boot we seed the
default Free / Pro / Agency tiers; subsequent boots are no-ops unless a plan
is explicitly missing.

Plan shape:
  {
    "id": "free" | "pro" | "agency" (or custom),
    "name": str,
    "price": float,                # EUR/mo
    "currency": "EUR",
    "interval": "month" | "year",
    "tagline": str,
    "features": [str, ...],        # marketing copy on /pricing
    "limits": {
        "apps": int,               # hard cap; -1 = unlimited
        "domains": int,            # hard cap; -1 = unlimited
        "workspaces": int,         # max Workspaces per account; -1 = unlimited
        "bandwidth_gb": int,       # fair-use bandwidth before credits kick in
        "build_minutes": int,      # fair-use build minutes
    },
    # NOTE: members per workspace AND projects per workspace are always
    # unlimited — no `members` or `projects` field.
    "credits": int,                # credits granted each billing cycle
    "highlight": bool,             # "recommended" badge on pricing page
    "order": int,                  # sort order
    "active": bool,                # show on pricing page
    "fleet_view": bool,            # exposes Agency Fleet dashboard
    "support_sla_hours": int,      # marketing only
  }
"""
import logging
from typing import Optional
from db import get_db

logger = logging.getLogger(__name__)


DEFAULT_PLANS = [
    {
        "id": "free",
        "name": "Free",
        "price": 0.0,
        "currency": "EUR",
        "interval": "month",
        "tagline": "For weekend projects.",
        "features": [
            "1 Workspace · 1 app",
            "1 custom domain · auto SSL",
            "100 GB bandwidth",
            "100 build minutes / mo",
            "Community support",
        ],
        "limits": {
            "apps": 1,
            "domains": 1,
            "workspaces": 1,
            "bandwidth_gb": 100,
            "build_minutes": 100,
        },
        "credits": 0,
        "highlight": False,
        "order": 1,
        "active": True,
        "fleet_view": False,
        "support_sla_hours": 0,
        "features_block": {"pageviews": True, "pagespeed": False, "heatmaps": False},
    },
    {
        "id": "starter",
        "name": "Starter",
        "price": 29.0,
        "currency": "EUR",
        "interval": "month",
        "tagline": "For solo devs and indie projects.",
        "features": [
            "1 Workspace · 3 apps",
            "3 custom domains · auto SSL",
            "250 GB bandwidth",
            "500 build minutes / mo",
            "Web analytics included",
            "25 credits / mo for add-ons",
            "Email support 48h",
        ],
        "limits": {
            "apps": 3,
            "domains": 3,
            "workspaces": 1,
            "bandwidth_gb": 250,
            "build_minutes": 500,
        },
        "credits": 25,
        "highlight": False,
        "order": 2,
        "active": True,
        "fleet_view": False,
        "support_sla_hours": 48,
        "features_block": {"pageviews": True, "pagespeed": True, "heatmaps": False},
    },
    {
        "id": "pro",
        "name": "Pro",
        "price": 99.0,
        "currency": "EUR",
        "interval": "month",
        "tagline": "Everything Vercel charges per-seat for. Flat.",
        "features": [
            "1 Workspace · unlimited members · unlimited projects",
            "10 apps · 10 custom domains",
            "1 TB bandwidth",
            "2.000 build minutes / mo",
            "Full observability — metrics, logs, alerts, heatmaps",
            "100 credits / mo for add-ons",
            "GitHub PR previews · Slack/Discord alerts",
            "Email support 24h",
        ],
        "limits": {
            "apps": 10,
            "domains": 10,
            "workspaces": 1,
            "bandwidth_gb": 1024,
            "build_minutes": 2000,
        },
        "credits": 100,
        "highlight": True,
        "order": 3,
        "active": True,
        "fleet_view": False,
        "support_sla_hours": 24,
        "features_block": {"pageviews": True, "pagespeed": True, "heatmaps": True},
    },
    {
        "id": "agency",
        "name": "Agency",
        "price": 299.0,
        "currency": "EUR",
        "interval": "month",
        "tagline": "For studios shipping for clients.",
        "features": [
            "Unlimited Workspaces (true isolation per brand)",
            "Unlimited members & projects per Workspace",
            "50 apps · unlimited custom domains",
            "5 TB bandwidth",
            "10.000 build minutes / mo",
            "Per-client billing · white-label PDF invoices",
            "500 credits / mo for add-ons",
            "1-year audit log · 99.9% uptime SLA",
            "Priority support 4h + Slack",
        ],
        "limits": {
            "apps": 50,
            "domains": -1,
            "workspaces": -1,
            "bandwidth_gb": 5120,
            "build_minutes": 10000,
        },
        "credits": 500,
        "highlight": False,
        "order": 4,
        "active": True,
        "fleet_view": True,
        "support_sla_hours": 4,
        "features_block": {"pageviews": True, "pagespeed": True, "heatmaps": True},
    },
]


async def seed_default_plans() -> None:
    """Insert default plans if missing. Safe to call repeatedly — never
    overwrites a plan that already exists, so admin edits survive restarts.

    Also backfills the `features_block` capability map on any plan that
    predates that field, so feature-gated routes don't break existing admins.
    """
    db = get_db()
    for plan in DEFAULT_PLANS:
        existing = await db.platform_plans.find_one({"id": plan["id"]}, {"_id": 0})
        if not existing:
            await db.platform_plans.insert_one(plan.copy())
            logger.info("seeded plan: %s", plan["id"])
            continue
        if "features_block" not in existing and "features_block" in plan:
            await db.platform_plans.update_one(
                {"id": plan["id"]},
                {"$set": {"features_block": plan["features_block"]}},
            )
            logger.info("backfilled features_block on plan: %s", plan["id"])
            continue
        # Keep features_block in sync with shipped defaults so newly-released
        # features (e.g. heatmaps for Pro) light up automatically — but never
        # downgrade a plan that's been manually edited to enable MORE features.
        cur_fb = existing.get("features_block") or {}
        target_fb = plan.get("features_block") or {}
        merged = {**target_fb, **{k: v for k, v in cur_fb.items() if v}}
        if merged != cur_fb:
            await db.platform_plans.update_one(
                {"id": plan["id"]},
                {"$set": {"features_block": merged}},
            )
            logger.info("expanded features_block on plan %s: %s", plan["id"], merged)


async def list_plans(*, only_active: bool = True) -> list[dict]:
    db = get_db()
    q = {"active": True} if only_active else {}
    plans = await db.platform_plans.find(q, {"_id": 0}).sort("order", 1).to_list(50)
    if not plans:
        # First-run safety net — should already have been seeded by server startup.
        await seed_default_plans()
        plans = await db.platform_plans.find(q, {"_id": 0}).sort("order", 1).to_list(50)
    return plans


async def get_plan(plan_id: str) -> Optional[dict]:
    db = get_db()
    # accept either id or legacy "hobby" → "free" name for backwards compat
    if plan_id == "hobby":
        plan_id = "free"
    return await db.platform_plans.find_one({"id": plan_id}, {"_id": 0})


async def update_plan(plan_id: str, updates: dict) -> Optional[dict]:
    db = get_db()
    safe_updates = {
        k: v for k, v in updates.items()
        if k in {
            "name", "price", "currency", "interval", "tagline", "features",
            "limits", "credits", "highlight", "order", "active",
            "fleet_view", "support_sla_hours", "features_block",
        }
    }
    if not safe_updates:
        return await get_plan(plan_id)
    await db.platform_plans.update_one({"id": plan_id}, {"$set": safe_updates})
    return await get_plan(plan_id)


async def workspace_plan(workspace_id: str) -> dict:
    """Resolve the plan a workspace is on. Plans live on the OWNER USER now —
    one plan per account, applies across every workspace the user owns. We
    keep this signature for backward compat with old callers."""
    db = get_db()
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0, "owner_id": 1, "plan": 1})
    plan_id = "free"
    if ws and ws.get("owner_id"):
        owner = await db.users.find_one({"id": ws["owner_id"]}, {"_id": 0, "plan": 1})
        plan_id = (owner or {}).get("plan") or ws.get("plan") or "free"
    elif ws:
        # Orphan workspace — fall back to legacy field.
        plan_id = ws.get("plan") or "free"
    plan = await get_plan(plan_id)
    if not plan:
        plan = await get_plan("free")
    return plan or {"id": "free", "limits": {"apps": 1, "domains": 1, "workspaces": 1, "bandwidth_gb": 100, "build_minutes": 100}, "credits": 0}


async def user_plan(user_id: str) -> dict:
    """Resolve a user's account-level plan. Replaces `workspace_plan` as the
    primary lookup — every workspace the user owns inherits this plan."""
    db = get_db()
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "plan": 1})
    plan_id = (u or {}).get("plan") or "free"
    plan = await get_plan(plan_id)
    if not plan:
        plan = await get_plan("free")
    return plan or {"id": "free", "limits": {"apps": 1, "domains": 1, "workspaces": 1, "bandwidth_gb": 100, "build_minutes": 100}, "credits": 0}


async def workspace_usage(workspace_id: str) -> dict:
    """Return current usage counters so we can show 'X/Y apps used' in the UI."""
    db = get_db()
    apps_used = await db.apps.count_documents({"workspace_id": workspace_id})
    domains_used = await db.domains.count_documents({"workspace_id": workspace_id})
    databases_used = await db.databases.count_documents({"workspace_id": workspace_id})
    return {
        "apps": apps_used,
        "domains": domains_used,
        "databases": databases_used,
        "workspaces": 1,  # this scope; account_usage gives the real count
    }


async def account_usage(user_id: str) -> dict:
    """Aggregate usage across every Workspace the user owns. Plan limits
    apply against this total (Agency = 50 apps total across all Workspaces)."""
    db = get_db()
    ws_ids = await db.workspaces.distinct("id", {"owner_id": user_id})
    if not ws_ids:
        return {"apps": 0, "domains": 0, "databases": 0, "workspaces": 0, "projects": 0}
    apps_used = await db.apps.count_documents({"workspace_id": {"$in": ws_ids}})
    domains_used = await db.domains.count_documents({"workspace_id": {"$in": ws_ids}})
    databases_used = await db.databases.count_documents({"workspace_id": {"$in": ws_ids}})
    projects_used = await db.projects.count_documents({"workspace_id": {"$in": ws_ids}})
    return {
        "apps": apps_used,
        "domains": domains_used,
        "databases": databases_used,
        "workspaces": len(ws_ids),
        "projects": projects_used,
    }


async def assert_limit(workspace_id: str, resource: str) -> None:
    """Raise HTTPException 402 if the OWNER's account-wide usage has hit the
    plan's limit on this resource. Plan + usage are account-scope now."""
    from fastapi import HTTPException
    db = get_db()
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0, "owner_id": 1})
    owner_id = (ws or {}).get("owner_id")
    if not owner_id:
        # Orphan workspace — fall back to workspace-scope (safer).
        plan = await workspace_plan(workspace_id)
        usage = await workspace_usage(workspace_id)
    else:
        plan = await user_plan(owner_id)
        usage = await account_usage(owner_id)
    cap = (plan.get("limits") or {}).get(resource)
    if cap is None or cap < 0:
        return  # unlimited
    current = usage.get(resource, 0)
    if current >= cap:
        plan_name = plan.get("name") or plan["id"]
        all_plans = await list_plans(only_active=True)
        higher = [p for p in all_plans if p.get("price", 0) > plan.get("price", 0)]
        suggestion = higher[0]["name"] if higher else None
        msg = (
            f"You hit your {plan_name} plan's {resource} limit ({cap}). "
            + (f"Upgrade to {suggestion} for more." if suggestion else "")
        )
        raise HTTPException(status_code=402, detail=msg)
