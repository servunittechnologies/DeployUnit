"""Resource sizing + DB-to-app connection routes.

Pattern: workspace member auth on per-app endpoints, admin-only on the
platform pricing endpoints. All resource changes go through `services.resources`
so the credit charges + build-engine push happen consistently.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from db import get_db
from auth_utils import get_current_user
from routers.workspaces import require_workspace_member
from services.resources import (
    DEFAULT_PLAN_RESOURCES, DEFAULT_PRICING,
    get_resource_config, save_resource_config,
    resolve_app_resources, set_app_addons,
    monthly_cost_for_addons,
)
from services.audit import log as audit_log
from clients.coolify import coolify

logger = logging.getLogger(__name__)
router = APIRouter(tags=["resources"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_db(d: dict) -> dict:
    """Strip credentials before sending a database doc to the UI."""
    out = {k: v for k, v in d.items() if k != "_id" and not k.startswith("internal_")}
    if out.get("connection_string"):
        # Mask password in UI representation
        cs = out["connection_string"]
        out["connection_string_masked"] = _mask_password(cs)
    return out


def _mask_password(connection_string: str) -> str:
    # postgres://user:pass@host:port/db → postgres://user:•••@host:port/db
    import re
    return re.sub(r"(://[^:]+:)([^@]+)(@)", r"\1•••\3", connection_string or "")


# ────────────────────── Resources ──────────────────────
class ResourceAddonsIn(BaseModel):
    extra_cpu_vcpu:   float = Field(ge=0, le=8, default=0)
    extra_memory_mb:  int   = Field(ge=0, le=32768, default=0)
    extra_storage_mb: int   = Field(ge=0, le=1048576, default=0)


@router.get("/apps/{app_id}/resources")
async def get_app_resources(app_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    bundle = await resolve_app_resources(app)
    cfg = await get_resource_config()
    return {
        **bundle,
        "pricing": cfg["pricing"],
        "plan_defaults_all": cfg["plan_defaults"],
    }


@router.put("/apps/{app_id}/resources")
async def update_app_resources(app_id: str, payload: ResourceAddonsIn, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin"])
    try:
        result = await set_app_addons(
            app_id,
            extra_cpu_vcpu=payload.extra_cpu_vcpu,
            extra_memory_mb=payload.extra_memory_mb,
            extra_storage_mb=payload.extra_storage_mb,
            actor=user,
            request=request,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


# ────────────────────── Database connections ──────────────────────
class AttachDatabaseIn(BaseModel):
    db_id: str
    env_var_name: str = Field(default="DATABASE_URL", min_length=1, max_length=80,
                              pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")


@router.get("/apps/{app_id}/connections")
async def list_app_connections(app_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user)
    conns = list(app.get("attached_databases") or [])
    # Enrich each entry with the current DB doc
    ids = [c["db_id"] for c in conns if c.get("db_id")]
    dbs = {}
    if ids:
        cur = db.databases.find({"id": {"$in": ids}}, {"_id": 0})
        async for d in cur:
            dbs[d["id"]] = d
    enriched = []
    for c in conns:
        dbdoc = dbs.get(c.get("db_id"))
        if not dbdoc:
            continue
        enriched.append({
            **c,
            "database": _safe_db(dbdoc),
        })
    # Also list candidate DBs the user could attach (same workspace, ready state)
    available = await db.databases.find(
        {"workspace_id": app["workspace_id"]}, {"_id": 0}
    ).to_list(50)
    return {
        "connections": enriched,
        "available_databases": [_safe_db(d) for d in available],
    }


@router.post("/apps/{app_id}/connections")
async def attach_database(app_id: str, payload: AttachDatabaseIn, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])
    dbdoc = await db.databases.find_one({"id": payload.db_id})
    if not dbdoc:
        raise HTTPException(status_code=404, detail="Database not found")
    if dbdoc["workspace_id"] != app["workspace_id"]:
        raise HTTPException(status_code=400, detail="Database belongs to a different workspace")
    # Reject duplicate env var name
    existing = app.get("attached_databases") or []
    if any(c.get("env_var_name") == payload.env_var_name for c in existing):
        raise HTTPException(status_code=409, detail=f"Env var '{payload.env_var_name}' is already attached to another DB on this app")
    new_conn = {
        "id": str(uuid.uuid4()),
        "db_id": payload.db_id,
        "env_var_name": payload.env_var_name,
        "attached_at": _now_iso(),
        "attached_by": user["id"],
    }
    await db.apps.update_one({"id": app_id}, {"$push": {"attached_databases": new_conn}})

    # Push the env var to the build engine so the next deploy injects it.
    if app.get("coolify_app_uuid") and dbdoc.get("connection_string"):
        try:
            await coolify.update_env(app["coolify_app_uuid"], {payload.env_var_name: dbdoc["connection_string"]})
        except Exception as e:
            logger.warning("attach: failed to push env var: %s", e)

    audit_log(action="app.db_attach", actor=user, workspace_id=app["workspace_id"],
              resource_type="app", resource_id=app_id,
              meta={"db_id": payload.db_id, "env": payload.env_var_name},
              request=request)
    return {"connection": new_conn, "database": _safe_db(dbdoc)}


@router.delete("/apps/{app_id}/connections/{conn_id}")
async def detach_database(app_id: str, conn_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])
    existing = app.get("attached_databases") or []
    conn = next((c for c in existing if c.get("id") == conn_id), None)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    await db.apps.update_one({"id": app_id}, {"$pull": {"attached_databases": {"id": conn_id}}})

    # Strip the env var from the build engine. Coolify update_env doesn't
    # delete; we set it to empty string which Coolify will remove on next
    # save. This is best-effort.
    if app.get("coolify_app_uuid"):
        try:
            await coolify.update_env(app["coolify_app_uuid"], {conn["env_var_name"]: ""})
        except Exception as e:
            logger.warning("detach: failed to clear env var: %s", e)

    audit_log(action="app.db_detach", actor=user, workspace_id=app["workspace_id"],
              resource_type="app", resource_id=app_id,
              meta={"conn_id": conn_id, "env": conn["env_var_name"]},
              request=request)
    return {"ok": True}


# ────────────────────── Admin pricing ──────────────────────
class PlanResourceIn(BaseModel):
    cpu_vcpu: float = Field(ge=0.05, le=64)
    memory_mb: int = Field(ge=64, le=131072)
    storage_mb: int = Field(ge=256, le=2097152)


class ResourceConfigIn(BaseModel):
    plan_defaults: Optional[dict[str, PlanResourceIn]] = None
    pricing: Optional[dict[str, float]] = None


async def _require_admin(request: Request):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    return user


@router.get("/admin/resource-config")
async def admin_get_resource_config(request: Request):
    await _require_admin(request)
    return await get_resource_config()


@router.put("/admin/resource-config")
async def admin_set_resource_config(payload: ResourceConfigIn, request: Request):
    user = await _require_admin(request)
    plan_defaults = None
    if payload.plan_defaults is not None:
        plan_defaults = {k: v.model_dump() for k, v in payload.plan_defaults.items()}
    pricing = None
    if payload.pricing is not None:
        # Coerce credit-cost fields to int so the admin UI doesn't render
        # decimals on integer credit amounts ('100.0 cr/mo' looks dumb).
        pricing = {}
        int_keys = {"cpu_credits_per_unit", "memory_credits_per_unit",
                    "storage_credits_per_unit", "memory_unit_mb", "storage_unit_mb"}
        for k, v in payload.pricing.items():
            pricing[k] = int(v) if k in int_keys else float(v)
    out = await save_resource_config(plan_defaults=plan_defaults, pricing=pricing)
    audit_log(action="admin.resource_config_update", actor=user,
              resource_type="platform", resource_id="settings",
              meta={"plan_defaults": plan_defaults, "pricing": pricing},
              request=request)
    return out


@router.get("/admin/resource-defaults")
async def admin_get_resource_defaults(request: Request):
    """Helper for the admin UI — the BUILT-IN baseline defaults so the admin
    can revert to them with a single click."""
    await _require_admin(request)
    return {
        "plan_defaults": DEFAULT_PLAN_RESOURCES,
        "pricing": DEFAULT_PRICING,
    }
