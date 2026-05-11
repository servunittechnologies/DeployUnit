"""Domains router — real DNS verification + Coolify FQDN sync.

Flow for the frontend wizard:
  1. POST /domains                 → create domain row, dns_verified=false
  2. GET  /domains/{id}/dns-target → returns the DNS record the user must add
  3. POST /domains/{id}/verify     → runs a live DNS lookup; if it points to
                                     our Coolify server, flips dns_verified=true
                                     and updates the Coolify application's
                                     fqdn so Traefik issues a Let's Encrypt
                                     cert. Returns current state for polling.
  4. DELETE /domains/{id}          → removes from Coolify + DB
"""
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
import dns.asyncresolver
import dns.resolver
import dns.exception
import httpx

from db import get_db
from auth_utils import get_current_user, require_workspace_member
from models import DomainIn
from clients.coolify import coolify
from routers.admin import get_platform_settings

router = APIRouter(tags=["domains"])
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _dns_target() -> dict:
    """Where users should point their DNS. Order of preference:
       1. platform_settings.default_subdomain_target_host (CNAME)
       2. platform_settings.default_subdomain_target_ip   (A record)
    Both are configured in Admin → Platform Domain.
    Returns {record_type: 'A'|'CNAME', value: str} or {record_type: None} if
    nothing is configured yet."""
    settings = await get_platform_settings()
    host = (settings.get("default_subdomain_target_host") or "").strip()
    ip = (settings.get("default_subdomain_target_ip") or "").strip()
    if host:
        return {"record_type": "CNAME", "value": host}
    if ip:
        return {"record_type": "A", "value": ip}
    return {"record_type": None, "value": None}


async def _resolve(domain: str, rtype: str) -> list[str]:
    """Best-effort DNS lookup. Returns empty list on any failure."""
    try:
        resolver = dns.asyncresolver.Resolver(configure=True)
        resolver.timeout = 4.0
        resolver.lifetime = 6.0
        answers = await resolver.resolve(domain, rtype)
        return [str(a).rstrip(".").strip() for a in answers]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, dns.exception.Timeout):
        return []
    except Exception as e:
        logger.warning("DNS %s lookup for %s failed: %s", rtype, domain, e)
        return []


async def _live_dns_check(domain: str, target: dict) -> dict:
    """Returns {resolves: bool, observed: [values], expected_type, expected_value, message}."""
    if not target or not target.get("record_type"):
        return {
            "resolves": False,
            "observed": [],
            "expected_type": None,
            "expected_value": None,
            "message": "Platform admin has not configured a DNS target yet.",
        }
    rtype = target["record_type"]
    expected = target["value"]
    # Always try A + CNAME so we give the user a useful "observed" response.
    a_records = await _resolve(domain, "A")
    cname_records = await _resolve(domain, "CNAME")
    observed = a_records + [f"CNAME→{c}" for c in cname_records]
    resolves = False
    if rtype == "A":
        resolves = expected in a_records
    elif rtype == "CNAME":
        # CNAME match can be direct CNAME value OR the resolved IP matches the
        # target's IP (if user set a different CNAME but it points to our host).
        resolves = any(c.rstrip(".") == expected.rstrip(".") for c in cname_records)
        if not resolves and a_records:
            # Fall back: resolve our expected host and compare IPs
            expected_ips = await _resolve(expected, "A")
            resolves = any(ip in a_records for ip in expected_ips)
    msg = "Resolved ✓" if resolves else (
        "DNS record not found yet — changes can take up to ~15 minutes to propagate."
        if not observed else
        f"Domain resolves but not to the DeployHub target ({rtype} {expected})."
    )
    return {
        "resolves": resolves,
        "observed": observed,
        "expected_type": rtype,
        "expected_value": expected,
        "message": msg,
    }


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
    # Enforce plan limit on domains
    from services.plans import assert_limit
    await assert_limit(app["workspace_id"], "domains")
    domain_clean = payload.domain.strip().lower().lstrip("http://").lstrip("https://").rstrip("/")
    if not domain_clean or " " in domain_clean or "." not in domain_clean:
        raise HTTPException(status_code=400, detail="Invalid domain")
    if await db.domains.find_one({"domain": domain_clean}):
        raise HTTPException(status_code=400, detail="Domain already linked")
    target = await _dns_target()
    doc = {
        "id": str(uuid.uuid4()),
        "app_id": payload.app_id,
        "workspace_id": app["workspace_id"],
        "domain": domain_clean,
        "dns_verified": False,
        "ssl_status": "pending",
        "coolify_fqdn_synced": False,
        "dns_target_type": target.get("record_type"),
        "dns_target_value": target.get("value"),
        "created_at": _now_iso(),
    }
    await db.domains.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/domains/{domain_id}/dns-target")
async def dns_target(domain_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    d = await db.domains.find_one({"id": domain_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    await require_workspace_member(d["workspace_id"], user)
    target = await _dns_target()
    # Decide whether user should add an A for the apex or a CNAME for a sub.
    is_apex = d["domain"].count(".") == 1  # naive but works for 99% of cases
    if target.get("record_type") == "CNAME" and is_apex:
        # Apex domains can't CNAME — fall back to A record if we also have an IP
        settings = await get_platform_settings()
        ip = (settings.get("default_subdomain_target_ip") or "").strip()
        if ip:
            target = {"record_type": "A", "value": ip}
    return {
        "domain": d["domain"],
        "record_type": target.get("record_type"),
        "record_name": "@" if is_apex else d["domain"].split(".")[0],
        "record_value": target.get("value"),
        "ttl": 300,
        "is_apex": is_apex,
        "verified": d.get("dns_verified", False),
        "ssl_status": d.get("ssl_status"),
    }


@router.post("/domains/{domain_id}/verify")
async def verify_domain(domain_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    d = await db.domains.find_one({"id": domain_id})
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    await require_workspace_member(d["workspace_id"], user, ["owner", "admin", "developer"])

    target = await _dns_target()
    check = await _live_dns_check(d["domain"], target)
    now = _now_iso()
    update = {
        "last_dns_check_at": now,
        "last_dns_check": check,
    }

    ssl_status = d.get("ssl_status")
    if check["resolves"]:
        update["dns_verified"] = True
        # Register the FQDN on Coolify (idempotent). Coolify/Traefik will
        # auto-issue a Let's Encrypt cert as soon as the host header matches.
        app = await db.apps.find_one({"id": d["app_id"]})
        if app and app.get("coolify_app_uuid") and coolify.configured:
            try:
                # Coolify supports multiple fqdn entries as a comma-separated
                # list on the application.fqdn field. We merge instead of
                # replacing to keep the default subdomain.
                existing = app.get("primary_url") or ""
                existing_hosts = []
                if existing:
                    # strip scheme for fqdn field
                    existing_hosts.append(existing.split("://")[-1].split("/")[0])
                target_url = f"https://{d['domain']}"
                if target_url.split("://")[-1] not in existing_hosts:
                    combined = ",".join([target_url] + [f"https://{h}" for h in existing_hosts if h])
                else:
                    combined = ",".join([target_url] + [f"https://{h}" for h in existing_hosts if h and h != d["domain"]])
                await coolify.update_application(app["coolify_app_uuid"], {"fqdn": combined})
                update["coolify_fqdn_synced"] = True
                ssl_status = "provisioning"
            except Exception as e:
                logger.warning("coolify fqdn sync failed for %s: %s", d["domain"], e)
                update["coolify_fqdn_sync_error"] = str(e)[:200]

    # SSL status: check if the domain now serves HTTPS cleanly
    if check["resolves"] and ssl_status in (None, "pending", "provisioning"):
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=False) as cli:
                r = await cli.get(f"https://{d['domain']}")
            if r.status_code < 500:
                ssl_status = "active"
        except Exception:
            pass  # leave as 'provisioning'
    update["ssl_status"] = ssl_status or "pending"

    await db.domains.update_one({"id": domain_id}, {"$set": update})
    doc = await db.domains.find_one({"id": domain_id}, {"_id": 0})
    return doc


@router.delete("/domains/{domain_id}")
async def delete_domain(domain_id: str, request: Request):
    user = await get_current_user(request)
    db = get_db()
    d = await db.domains.find_one({"id": domain_id})
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    await require_workspace_member(d["workspace_id"], user, ["owner", "admin", "developer"])

    # Best-effort cleanup in Coolify — strip this fqdn from the app.
    if d.get("coolify_fqdn_synced"):
        app = await db.apps.find_one({"id": d["app_id"]})
        if app and app.get("coolify_app_uuid") and coolify.configured:
            try:
                current = await coolify._request("GET", f"/applications/{app['coolify_app_uuid']}")
                existing = (current or {}).get("fqdn") or ""
                remaining = ",".join(
                    u for u in existing.split(",")
                    if u.strip() and d["domain"] not in u
                )
                await coolify.update_application(app["coolify_app_uuid"], {"fqdn": remaining})
            except Exception as e:
                logger.warning("coolify fqdn removal for %s failed: %s", d["domain"], e)

    await db.domains.delete_one({"id": domain_id})
    return {"deleted": True}
