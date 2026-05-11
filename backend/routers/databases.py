"""Managed databases (Postgres / Redis / MySQL / MariaDB / MongoDB).

Provisions a database via Coolify and stores a thin reference locally. The
actual container is owned by Coolify; we keep credentials Fernet-encrypted
because anyone with the workspace can read them through the UI.

Schema (db.databases):
  id, workspace_id, type (postgresql/redis/mysql/mariadb/mongodb),
  name, version, status, coolify_db_uuid (nullable while provisioning),
  connection_string_enc (Fernet), internal_host, public_port, created_at.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from clients.coolify import coolify
from services.audit import log as audit_log
from crypto_utils import encrypt_token, decrypt_token

router = APIRouter(tags=["databases"])
logger = logging.getLogger(__name__)

SUPPORTED_TYPES = {
    "postgresql": {"label": "PostgreSQL", "default_version": "16", "port": 5432},
    "redis":      {"label": "Redis",      "default_version": "7",  "port": 6379},
    "mysql":      {"label": "MySQL",      "default_version": "8",  "port": 3306},
    "mariadb":    {"label": "MariaDB",    "default_version": "11", "port": 3306},
    "mongodb":    {"label": "MongoDB",    "default_version": "7",  "port": 27017},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DatabaseIn(BaseModel):
    type: str
    name: str
    version: Optional[str] = None


def _redact(doc: dict) -> dict:
    """Strip the encrypted blob; the UI uses /reveal to get the live URL."""
    out = dict(doc)
    out.pop("connection_string_enc", None)
    out["connection_string_set"] = bool(doc.get("connection_string_enc"))
    return out


@router.get("/databases")
async def list_databases(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    rows = await get_db().databases.find({"workspace_id": workspace_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"databases": [_redact(r) for r in rows], "supported_types": SUPPORTED_TYPES}


@router.post("/databases")
async def create_database(payload: DatabaseIn, workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user, ["owner", "admin", "developer"])
    if payload.type not in SUPPORTED_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(SUPPORTED_TYPES.keys())}")
    db = get_db()
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    version = payload.version or SUPPORTED_TYPES[payload.type]["default_version"]

    record = {
        "id": str(uuid.uuid4()),
        "workspace_id": workspace_id,
        "type": payload.type,
        "name": name,
        "version": version,
        "status": "provisioning",
        "coolify_db_uuid": None,
        "connection_string_enc": None,
        "internal_host": None,
        "public_port": None,
        "created_at": _now_iso(),
    }

    # Best-effort Coolify provisioning. If the engine is offline we still
    # persist the record so the UI shows "provisioning" and a retry can pick
    # it up later.
    ws = await db.workspaces.find_one({"id": workspace_id})
    project_uuid = (ws or {}).get("coolify_project_uuid")
    server_uuid = await coolify.get_default_server_uuid() if coolify.configured else None
    if coolify.configured and server_uuid and project_uuid:
        res = await coolify.create_database(
            server_uuid=server_uuid, project_uuid=project_uuid,
            environment_name="production", db_type=payload.type,
            name=name, version=version,
        )
        if res:
            cool_uuid = res.get("uuid") or (res.get("data") or {}).get("uuid")
            conn = res.get("internal_db_url") or res.get("internal_connection_url") or res.get("connection_url")
            if cool_uuid:
                record["coolify_db_uuid"] = cool_uuid
                # Coolify creates databases stopped — auto-start so the
                # connection string is actually usable.
                try:
                    await coolify.start_database(cool_uuid)
                    record["status"] = "running"
                except Exception as e:
                    logger.warning("coolify auto-start_database failed: %s", e)
                    record["status"] = "stopped"
            if conn:
                record["connection_string_enc"] = encrypt_token(conn)
    else:
        logger.info("databases: Coolify not configured/server-uuid missing, skipping provisioning")

    await db.databases.insert_one(dict(record))
    audit_log(
        action="database.create", actor=user, workspace_id=workspace_id,
        resource_type="database", resource_id=record["id"],
        meta={"type": payload.type, "name": name, "version": version},
        request=request,
    )
    record.pop("_id", None)
    return _redact(record)


@router.post("/databases/{db_id}/reveal")
async def reveal_connection(db_id: str, request: Request):
    """Decrypt and return the connection string for this workspace's UI.
    Audited so leaks are traceable."""
    user = await get_current_user(request)
    doc = await get_db().databases.find_one({"id": db_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Database not found")
    await require_workspace_member(doc["workspace_id"], user, ["owner", "admin", "developer"])
    if not doc.get("connection_string_enc"):
        return {"connection_string": None, "reason": "not provisioned yet"}
    try:
        url = decrypt_token(doc["connection_string_enc"])
    except Exception:
        return {"connection_string": None, "reason": "decrypt failed"}
    audit_log(
        action="database.reveal_connection", actor=user, workspace_id=doc["workspace_id"],
        resource_type="database", resource_id=db_id, request=request,
    )
    return {"connection_string": url}


@router.post("/databases/{db_id}/start")
async def start_database(db_id: str, request: Request):
    user = await get_current_user(request)
    doc = await get_db().databases.find_one({"id": db_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Database not found")
    await require_workspace_member(doc["workspace_id"], user, ["owner", "admin", "developer"])
    if doc.get("coolify_db_uuid"):
        await coolify.start_database(doc["coolify_db_uuid"])
    await get_db().databases.update_one({"id": db_id}, {"$set": {"status": "running"}})
    audit_log(action="database.start", actor=user, workspace_id=doc["workspace_id"],
              resource_type="database", resource_id=db_id, request=request)
    return {"status": "running"}


@router.post("/databases/{db_id}/stop")
async def stop_database(db_id: str, request: Request):
    user = await get_current_user(request)
    doc = await get_db().databases.find_one({"id": db_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Database not found")
    await require_workspace_member(doc["workspace_id"], user, ["owner", "admin", "developer"])
    if doc.get("coolify_db_uuid"):
        await coolify.stop_database(doc["coolify_db_uuid"])
    await get_db().databases.update_one({"id": db_id}, {"$set": {"status": "stopped"}})
    audit_log(action="database.stop", actor=user, workspace_id=doc["workspace_id"],
              resource_type="database", resource_id=db_id, request=request)
    return {"status": "stopped"}


@router.delete("/databases/{db_id}")
async def delete_database(db_id: str, request: Request):
    user = await get_current_user(request)
    doc = await get_db().databases.find_one({"id": db_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Database not found")
    await require_workspace_member(doc["workspace_id"], user, ["owner", "admin", "developer"])
    if doc.get("coolify_db_uuid"):
        try:
            await coolify.delete_database(doc["coolify_db_uuid"])
        except Exception as e:
            logger.warning("coolify delete_database failed: %s", e)
    await get_db().databases.delete_one({"id": db_id})
    audit_log(action="database.delete", actor=user, workspace_id=doc["workspace_id"],
              resource_type="database", resource_id=db_id,
              meta={"name": doc.get("name")}, request=request)
    return {"deleted": True}
