"""Domains routes."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from models import DomainIn
from clients.whmcs import whmcs

router = APIRouter(tags=["domains"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/domains")
async def list_domains(workspace_id: str, request: Request):
    user = await get_current_user(request)
    await require_workspace_member(workspace_id, user)
    db = get_db()
    return await db.domains.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(200)


@router.post("/domains")
async def add_domain(payload: DomainIn, request: Request):
    user = await get_current_user(request)
    db = get_db()
    app = await db.apps.find_one({"id": payload.app_id})
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    await require_workspace_member(app["workspace_id"], user, ["owner", "admin", "developer"])
    domain_clean = payload.domain.strip().lower()
    if not domain_clean or " " in domain_clean:
        raise HTTPException(status_code=400, detail="Invalid domain")
    if await db.domains.find_one({"domain": domain_clean}):
        raise HTTPException(status_code=400, detail="Domain already linked")
    doc = {
        "id": str(uuid.uuid4()),
        "app_id": payload.app_id,
        "workspace_id": app["workspace_id"],
        "domain": domain_clean,
        "dns_verified": False,
        "ssl_status": "pending",
        "created_at": _now_iso(),
    }
    await db.domains.insert_one(doc)
    return doc


@router.delete("/domains/{domain_id}")
async def delete_domain(domain_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    d = await db.domains.find_one({"id": domain_id})
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    await require_workspace_member(d["workspace_id"], user, ["owner", "admin", "developer"])
    await db.domains.delete_one({"id": domain_id})
    return {"deleted": True}


@router.post("/domains/{domain_id}/verify")
async def verify_domain(domain_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    d = await db.domains.find_one({"id": domain_id})
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    await require_workspace_member(d["workspace_id"], user, ["owner", "admin", "developer"])
    # Mock DNS verification — in production we'd run a DNS A-record check.
    await db.domains.update_one(
        {"id": domain_id}, {"$set": {"dns_verified": True, "ssl_status": "active"}}
    )
    return {"dns_verified": True, "ssl_status": "active"}


@router.get("/domains/whois")
async def whois(domain: str, request: Request):
    await get_current_user(request)
    res = await whmcs.domain_whois(domain)
    return res
