"""Per-app resource sizing + credit-based addon billing.

Concept:
  * Every plan has DEFAULT resources (CPU/MEM/STORAGE) per app.
  * Users can stack ADDONS on top of the plan default (extra CPU, extra MEM,
    extra storage) — each addon costs credits per month.
  * Both defaults and addon pricing live in `platform_settings` so the admin
    can tweak without code changes.
  * On every deploy we push the resolved limits to the build engine via
    `coolify.update_application` (`limits_cpus`, `limits_memory`).
  * `monthly_grant_tick` (cron, daily) charges due-addons; if the user's
    wallet runs out we auto-downgrade addons to zero on the affected apps
    and notify them.
  * Plan changes recompute the cost of every app the user owns; downgrades
    refund the pro-rated unused plan price back to the credit wallet.
"""
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Optional, TypedDict

from db import get_db
from services.audit import log as audit_log
from services.plans import user_plan, get_plan

logger = logging.getLogger(__name__)


PLATFORM_SETTINGS_ID = "platform-singleton"


# ─────────────────────── Defaults ───────────────────────
class ResourceBundle(TypedDict):
    cpu_vcpu: float
    memory_mb: int
    storage_mb: int


DEFAULT_PLAN_RESOURCES: dict[str, ResourceBundle] = {
    "free":   {"cpu_vcpu": 0.25, "memory_mb": 256,  "storage_mb": 1024},
    "pro":    {"cpu_vcpu": 0.5,  "memory_mb": 512,  "storage_mb": 5120},
    "agency": {"cpu_vcpu": 1.0,  "memory_mb": 1024, "storage_mb": 20480},
}

# Credit cost per addon UNIT per month. A unit is the granularity the user
# can buy at — bigger units mean simpler pricing for the customer.
#   cpu unit = +0.5 vCPU
#   mem unit = +512 MB
#   storage unit = +5 GB (5120 MB)
DEFAULT_PRICING = {
    "cpu_credits_per_unit":     100,   # 100 credits / 0.5 vCPU / month
    "cpu_unit_vcpu":            0.5,
    "memory_credits_per_unit":  50,    # 50 credits / 512 MB / month
    "memory_unit_mb":           512,
    "storage_credits_per_unit": 25,    # 25 credits / 5 GB / month
    "storage_unit_mb":          5120,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────── Settings I/O ───────────────────────
async def get_resource_config() -> dict:
    """Return current plan-defaults + pricing, merged with admin overrides
    from platform_settings.resource_config."""
    db = get_db()
    doc = await db.platform_settings.find_one({"id": PLATFORM_SETTINGS_ID}, {"_id": 0}) or {}
    rc = doc.get("resource_config") or {}
    plan_defaults = rc.get("plan_defaults") or {}
    pricing = rc.get("pricing") or {}
    return {
        "plan_defaults": {**DEFAULT_PLAN_RESOURCES, **plan_defaults},
        "pricing": {**DEFAULT_PRICING, **pricing},
    }


async def save_resource_config(*, plan_defaults: Optional[dict] = None, pricing: Optional[dict] = None) -> dict:
    db = get_db()
    update = {}
    if plan_defaults is not None:
        update["resource_config.plan_defaults"] = plan_defaults
    if pricing is not None:
        update["resource_config.pricing"] = pricing
    if update:
        await db.platform_settings.update_one(
            {"id": PLATFORM_SETTINGS_ID},
            {"$set": update,
             "$setOnInsert": {"id": PLATFORM_SETTINGS_ID, "created_at": _now_iso()}},
            upsert=True,
        )
    return await get_resource_config()


# ─────────────────────── App-side ───────────────────────
async def plan_defaults_for_workspace(workspace_id: str) -> ResourceBundle:
    """Resolve the plan defaults the workspace owner is currently on."""
    db = get_db()
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0, "owner_id": 1})
    if not ws or not ws.get("owner_id"):
        return DEFAULT_PLAN_RESOURCES["free"]
    plan = await user_plan(ws["owner_id"])
    cfg = await get_resource_config()
    return cfg["plan_defaults"].get(plan["id"]) or DEFAULT_PLAN_RESOURCES["free"]


async def resolve_app_resources(app: dict) -> dict:
    """Compute the EFFECTIVE limits for an app:
        plan_default + addons (clamped to ≥0).

    Returns a dict with current/default/addons/monthly_cost_credits — used
    by both the API response shape and the actual deploy-time enforcement.
    """
    defaults = await plan_defaults_for_workspace(app["workspace_id"])
    addons = app.get("resource_addons") or {"cpu_vcpu": 0, "memory_mb": 0, "storage_mb": 0}
    eff = {
        "cpu_vcpu":   max(0.05, float(defaults["cpu_vcpu"]) + float(addons.get("cpu_vcpu") or 0)),
        "memory_mb":  max(64,  int(defaults["memory_mb"]) + int(addons.get("memory_mb") or 0)),
        "storage_mb": max(256, int(defaults["storage_mb"]) + int(addons.get("storage_mb") or 0)),
    }
    cost = await monthly_cost_for_addons(addons)
    return {
        "plan_default": defaults,
        "addons": {
            "cpu_vcpu":   float(addons.get("cpu_vcpu") or 0),
            "memory_mb":  int(addons.get("memory_mb") or 0),
            "storage_mb": int(addons.get("storage_mb") or 0),
        },
        "effective": eff,
        "monthly_cost_credits": cost,
        "addons_active_since": app.get("resource_addons_since"),
    }


async def monthly_cost_for_addons(addons: dict) -> int:
    """Sum-up credit cost for a given addon bundle."""
    if not addons:
        return 0
    cfg = await get_resource_config()
    p = cfg["pricing"]
    cpu_units    = max(0, math.ceil((float(addons.get("cpu_vcpu") or 0))   / p["cpu_unit_vcpu"]))
    memory_units = max(0, math.ceil((int(addons.get("memory_mb") or 0))     / p["memory_unit_mb"]))
    storage_units = max(0, math.ceil((int(addons.get("storage_mb") or 0))   / p["storage_unit_mb"]))
    return (cpu_units * p["cpu_credits_per_unit"]
            + memory_units * p["memory_credits_per_unit"]
            + storage_units * p["storage_credits_per_unit"])


# ─────────────────────── Mutate addons ───────────────────────
async def set_app_addons(
    app_id: str,
    *,
    extra_cpu_vcpu: float,
    extra_memory_mb: int,
    extra_storage_mb: int,
    actor: dict,
    request=None,
) -> dict:
    """Set the addon bundle on an app. Charges the DIFFERENCE in monthly
    cost vs. the current bundle, pro-rated for the rest of the period if
    upgrading (down-billing is a wait-til-next-period thing — keeps the
    book-keeping simple)."""
    from services.credits import consume_credits, grant_credits
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise ValueError("app not found")
    ws = await db.workspaces.find_one({"id": app["workspace_id"]}, {"_id": 0, "owner_id": 1})
    owner_id = (ws or {}).get("owner_id")
    if not owner_id:
        raise ValueError("workspace has no owner")

    current = app.get("resource_addons") or {"cpu_vcpu": 0, "memory_mb": 0, "storage_mb": 0}
    new_addons = {
        "cpu_vcpu":   max(0.0, float(extra_cpu_vcpu)),
        "memory_mb":  max(0,   int(extra_memory_mb)),
        "storage_mb": max(0,   int(extra_storage_mb)),
    }
    old_cost = await monthly_cost_for_addons(current)
    new_cost = await monthly_cost_for_addons(new_addons)
    delta = new_cost - old_cost

    update = {
        "resource_addons": new_addons,
        "resource_addons_since": _now_iso() if any(new_addons.values()) else None,
        "monthly_resource_cost": new_cost,
    }
    # Pro-rated charge: rest of period as a fraction (we use 30-day period).
    period_days = 30
    days_left = _days_left_in_period(app.get("resource_addons_charged_at"))
    if delta > 0 and days_left:
        prorated = math.ceil(delta * days_left / period_days)
        if prorated > 0:
            await consume_credits(
                owner_id, prorated,
                reason=f"resource upgrade on '{app.get('name')}' (pro-rated {days_left}d of {period_days})",
                ref_id=app_id, ref_type="resource_addon",
                user_id=actor["id"],
            )
    elif delta < 0 and days_left:
        # Refund the pro-rated DOWNGRADE amount back to credits.
        refund = math.floor((-delta) * days_left / period_days)
        if refund > 0:
            await grant_credits(
                owner_id, refund,
                reason=f"resource downgrade refund on '{app.get('name')}' (pro-rated {days_left}d of {period_days})",
                type_="refund",
                ref_id=app_id, ref_type="resource_addon",
                user_id=actor["id"],
            )

    # First-time charge starts the billing period
    if old_cost == 0 and new_cost > 0:
        update["resource_addons_charged_at"] = _now_iso()
    elif new_cost == 0:
        update["resource_addons_charged_at"] = None

    await db.apps.update_one({"id": app_id}, {"$set": update})
    audit_log(
        action="app.resources_update",
        actor=actor,
        workspace_id=app["workspace_id"],
        resource_type="app",
        resource_id=app_id,
        meta={"old": current, "new": new_addons, "delta_credits": delta,
              "old_cost": old_cost, "new_cost": new_cost},
        request=request,
    )

    # Apply to the build engine immediately so the user can see it take
    # effect on the next deploy (or via the runtime container limits).
    try:
        await push_resources_to_build_engine(app_id)
    except Exception as e:
        logger.warning("push_resources_to_build_engine failed for %s: %s", app_id, e)

    return await resolve_app_resources({**app, **update})


def _days_left_in_period(charged_at_iso: Optional[str], period_days: int = 30) -> int:
    if not charged_at_iso:
        return period_days
    try:
        charged_at = datetime.fromisoformat(charged_at_iso.replace("Z", "+00:00"))
    except Exception:
        return period_days
    elapsed = (datetime.now(timezone.utc) - charged_at).total_seconds() / 86400.0
    left = max(0, period_days - elapsed)
    return int(left)


# ─────────────────────── Build engine enforcement ───────────────────────
async def push_resources_to_build_engine(app_id: str) -> None:
    """Update the Coolify application limits to match the app's resolved
    cpu/memory bundle. Storage is a separate concept (persistent volumes) —
    we expose it but don't enforce automatically yet."""
    from clients.coolify import coolify
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app or not app.get("coolify_app_uuid"):
        return
    res = await resolve_app_resources(app)
    eff = res["effective"]
    payload = {
        # Coolify v4 application schema:
        #   limits_memory:        string like "512m"
        #   limits_memory_swap:   string
        #   limits_cpus:          string like "0.5"
        "limits_memory":      f"{int(eff['memory_mb'])}m",
        "limits_memory_swap": f"{int(eff['memory_mb']) * 2}m",
        "limits_cpus":        f"{float(eff['cpu_vcpu']):.2f}",
    }
    await coolify.update_application(app["coolify_app_uuid"], payload)
    logger.info("pushed resources to build engine for %s: %s", app_id, payload)


# ─────────────────────── Monthly billing job ───────────────────────
async def charge_due_addons() -> dict:
    """Walk every app that has addon-cost > 0 and is due (>=30 days since last
    charge). On insufficient credits → auto-downgrade addons to zero and log
    an alert notification for the workspace owner."""
    from services.credits import consume_credits
    db = get_db()
    now = datetime.now(timezone.utc)
    cutoff = (now.timestamp() - 30 * 86400)
    charged = 0
    failed = 0
    cursor = db.apps.find(
        {"monthly_resource_cost": {"$gt": 0}}, {"_id": 0}
    )
    async for app in cursor:
        last = app.get("resource_addons_charged_at")
        if last:
            try:
                last_ts = datetime.fromisoformat(last.replace("Z", "+00:00")).timestamp()
            except Exception:
                last_ts = 0
            if last_ts > cutoff:
                continue  # not due yet
        ws = await db.workspaces.find_one({"id": app["workspace_id"]}, {"_id": 0, "owner_id": 1, "name": 1})
        owner_id = (ws or {}).get("owner_id")
        if not owner_id:
            continue
        cost = int(app["monthly_resource_cost"])
        try:
            await consume_credits(
                owner_id, cost,
                reason=f"monthly resource addons on '{app.get('name')}'",
                ref_id=app["id"], ref_type="resource_addon_monthly",
            )
            await db.apps.update_one(
                {"id": app["id"]},
                {"$set": {"resource_addons_charged_at": now.isoformat()}},
            )
            charged += 1
        except Exception as e:
            logger.info("resource billing fail for %s: %s — auto-downgrading", app["id"], e)
            failed += 1
            await db.apps.update_one(
                {"id": app["id"]},
                {"$set": {"resource_addons": {"cpu_vcpu": 0, "memory_mb": 0, "storage_mb": 0},
                          "monthly_resource_cost": 0,
                          "resource_addons_charged_at": None,
                          "resource_addons_auto_downgraded_at": now.isoformat()}},
            )
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": owner_id,
                "workspace_id": app["workspace_id"],
                "title": f"Resource addons removed from {app.get('name')}",
                "body": (
                    "We couldn't charge the monthly credit cost for the extra CPU/memory/storage "
                    f"on '{app.get('name')}'. The app has dropped back to its plan-default resources. "
                    "Top up credits on your Account page to restore them."
                ),
                "kind": "resource_downgrade",
                "read": False,
                "created_at": now.isoformat(),
            })
            try:
                await push_resources_to_build_engine(app["id"])
            except Exception:
                pass
    return {"charged": charged, "auto_downgraded": failed, "ran_at": now.isoformat()}


async def refund_plan_downgrade(user_id: str, *, from_plan_id: str, to_plan_id: str) -> int:
    """When the user drops to a cheaper plan mid-period, refund the unused
    portion of the OLD plan's flat fee back into their credit wallet.

    Returns the credit amount refunded (0 if not applicable).
    """
    from services.credits import grant_credits
    db = get_db()
    sub = await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0})
    started_at = (sub or {}).get("started_at")
    if not started_at:
        return 0
    try:
        sub_start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except Exception:
        return 0
    old_plan = await get_plan(from_plan_id)
    new_plan = await get_plan(to_plan_id) or {}
    if not old_plan:
        return 0
    old_price = float(old_plan.get("price") or 0)
    new_price = float(new_plan.get("price") or 0)
    if old_price <= new_price:
        return 0
    # Pro-rated unused fraction of the month
    elapsed = (datetime.now(timezone.utc) - sub_start).total_seconds() / 86400.0
    days_left = max(0.0, 30 - elapsed)
    if days_left <= 0:
        return 0
    diff_eur = (old_price - new_price) * (days_left / 30.0)
    # Convert € to credits at the standard rate (1 credit ≈ €0.10).
    refund_credits = int(round(diff_eur * 10))
    if refund_credits <= 0:
        return 0
    await grant_credits(
        user_id, refund_credits,
        reason=f"plan downgrade refund ({from_plan_id} → {to_plan_id}, {int(days_left)}d unused)",
        type_="refund",
        ref_type="plan_downgrade",
    )
    return refund_credits
