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
        "team": int,               # team-member cap; -1 = unlimited
        "bandwidth_gb": int,       # fair-use bandwidth before credits kick in
        "build_minutes": int,      # fair-use build minutes
    },
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
            "1 app",
            "1 custom domain",
            "100 GB bandwidth",
            "100 build minutes / mo",
            "Auto SSL + custom domains",
            "Community support",
        ],
        "limits": {
            "apps": 1,
            "domains": 1,
            "team": 1,
            "bandwidth_gb": 100,
            "build_minutes": 100,
        },
        "credits": 0,
        "highlight": False,
        "order": 1,
        "active": True,
        "fleet_view": False,
        "support_sla_hours": 0,  # community
    },
    {
        "id": "pro",
        "name": "Pro",
        "price": 20.0,
        "currency": "EUR",
        "interval": "month",
        "tagline": "Everything Vercel charges per-seat for. Flat.",
        "features": [
            "Unlimited team seats",
            "10 apps",
            "500 GB bandwidth",
            "1.000 build minutes / mo",
            "50 credits / mo (≈50 SMS alerts)",
            "GitHub webhooks · PR previews",
            "Branch protection · Slack/Discord alerts",
            "Email support 24h",
        ],
        "limits": {
            "apps": 10,
            "domains": 10,
            "team": -1,
            "bandwidth_gb": 500,
            "build_minutes": 1000,
        },
        "credits": 50,
        "highlight": True,
        "order": 2,
        "active": True,
        "fleet_view": False,
        "support_sla_hours": 24,
    },
    {
        "id": "agency",
        "name": "Agency",
        "price": 99.0,
        "currency": "EUR",
        "interval": "month",
        "tagline": "For studios shipping for clients.",
        "features": [
            "Unlimited team seats",
            "50 apps",
            "2 TB bandwidth",
            "5.000 build minutes / mo",
            "250 credits / mo (≈250 SMS alerts)",
            "Unlimited workspaces (host every client separately)",
            "1-year audit log",
            "Priority support 4h + Slack",
            "99.9% uptime SLA",
        ],
        "limits": {
            "apps": 50,
            "domains": -1,
            "team": -1,
            "bandwidth_gb": 2048,
            "build_minutes": 5000,
        },
        "credits": 250,
        "highlight": False,
        "order": 3,
        "active": True,
        "fleet_view": True,
        "support_sla_hours": 4,
    },
]


async def seed_default_plans() -> None:
    """Insert default plans if missing. Safe to call repeatedly — never
    overwrites a plan that already exists, so admin edits survive restarts."""
    db = get_db()
    for plan in DEFAULT_PLANS:
        existing = await db.platform_plans.find_one({"id": plan["id"]}, {"_id": 0, "id": 1})
        if not existing:
            await db.platform_plans.insert_one(plan.copy())
            logger.info("seeded plan: %s", plan["id"])


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
            "fleet_view", "support_sla_hours",
        }
    }
    if not safe_updates:
        return await get_plan(plan_id)
    await db.platform_plans.update_one({"id": plan_id}, {"$set": safe_updates})
    return await get_plan(plan_id)


async def workspace_plan(workspace_id: str) -> dict:
    """Resolve the plan a workspace is on. Defaults to Free if no match
    (helpful during migrations / data drift)."""
    db = get_db()
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0, "plan": 1})
    plan_id = (ws or {}).get("plan") or "free"
    plan = await get_plan(plan_id)
    if not plan:
        plan = await get_plan("free")
    return plan or {"id": "free", "limits": {"apps": 1, "domains": 1, "team": 1, "bandwidth_gb": 100, "build_minutes": 100}, "credits": 0}


async def workspace_usage(workspace_id: str) -> dict:
    """Return current usage counters so we can show 'X/Y apps used' in the UI."""
    db = get_db()
    apps_used = await db.apps.count_documents({"workspace_id": workspace_id})
    domains_used = await db.domains.count_documents({"workspace_id": workspace_id})
    # 1 (owner) + count of workspace_members rows
    member_rows = await db.workspace_members.count_documents({"workspace_id": workspace_id})
    members_used = 1 + member_rows
    return {
        "apps": apps_used,
        "domains": domains_used,
        "team": members_used,
    }


async def assert_limit(workspace_id: str, resource: str) -> None:
    """Raise HTTPException 402 with a helpful message if the workspace has
    hit its plan's limit on this resource."""
    from fastapi import HTTPException
    plan = await workspace_plan(workspace_id)
    cap = (plan.get("limits") or {}).get(resource)
    if cap is None or cap < 0:
        return  # unlimited
    usage = await workspace_usage(workspace_id)
    current = usage.get(resource, 0)
    if current >= cap:
        plan_name = plan.get("name") or plan["id"]
        # Suggest the next active plan in price order
        all_plans = await list_plans(only_active=True)
        higher = [p for p in all_plans if p.get("price", 0) > plan.get("price", 0)]
        suggestion = higher[0]["name"] if higher else None
        msg = (
            f"You hit your {plan_name} plan's {resource} limit ({cap}). "
            + (f"Upgrade to {suggestion} for more." if suggestion else "")
        )
        raise HTTPException(status_code=402, detail=msg)
