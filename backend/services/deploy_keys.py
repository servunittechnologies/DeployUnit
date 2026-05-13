"""Deploy-key automation: generate ed25519 keypair, add it to a GitHub repo as
a read-only deploy key, and register the private half in Coolify as a git-
related private key. Lets DeployUnit deploy private GitHub repos end-to-end
without the user ever touching Coolify.

Reused on:
  * first-time app creation (private repo detected)
  * app deletion (cleanup both sides)
"""
import logging
import re
from typing import Optional

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

logger = logging.getLogger(__name__)


def generate_deploy_keypair() -> tuple[str, str]:
    """Return (private_openssh_pem, public_openssh). Ed25519 — small, fast,
    GitHub-supported."""
    priv = Ed25519PrivateKey.generate()
    private_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_openssh = priv.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ).decode()
    return private_pem, public_openssh


async def add_github_deploy_key(
    owner: str, repo: str, title: str, public_key: str, user_token: str
) -> Optional[int]:
    """POST a deploy key to the GitHub repo. Returns the numeric key id,
    or None on failure. Uses the caller's OAuth token (repo scope required).

    Env guard: blocked on preview. Preview must never push deploy keys to
    real customer repos — those would persist outside our system and could
    be used by a stale preview backend to clone private code.
    """
    if not user_token:
        return None
    from env_utils import is_production, env_name
    if not is_production():
        logger.info("[env-guard] GitHub add_deploy_key %s/%s skipped (env=%s)", owner, repo, env_name())
        return None
    url = f"https://api.github.com/repos/{owner}/{repo}/keys"
    try:
        async with httpx.AsyncClient(timeout=12.0) as cli:
            r = await cli.post(
                url,
                headers={
                    "Authorization": f"Bearer {user_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={"title": title, "key": public_key, "read_only": True},
            )
        if r.status_code in (201, 200):
            return (r.json() or {}).get("id")
        # 422: key already exists → look it up and return its id for idempotency
        if r.status_code == 422 and "already in use" in r.text.lower():
            found = await _find_existing_deploy_key(owner, repo, public_key, user_token)
            if found:
                return found
        logger.warning("add_github_deploy_key %s/%s → %s %s", owner, repo, r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("add_github_deploy_key %s/%s failed: %s", owner, repo, e)
    return None


async def _find_existing_deploy_key(
    owner: str, repo: str, public_key: str, user_token: str
) -> Optional[int]:
    target_fingerprint = _public_key_body(public_key)
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.get(
                f"https://api.github.com/repos/{owner}/{repo}/keys",
                headers={
                    "Authorization": f"Bearer {user_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        if r.status_code == 200:
            for k in r.json() or []:
                if _public_key_body(k.get("key", "")) == target_fingerprint:
                    return k.get("id")
    except Exception:
        pass
    return None


def _public_key_body(pubkey: str) -> str:
    """Return just the base64 body part of an OpenSSH public key (middle token),
    used to match keys for de-duplication. Tolerant of missing/extra comments."""
    parts = (pubkey or "").strip().split()
    if len(parts) >= 2:
        return parts[1]
    return pubkey.strip()


async def remove_github_deploy_key(
    owner: str, repo: str, key_id: int, user_token: str
) -> bool:
    if not user_token or not key_id:
        return False
    from env_utils import is_production, env_name
    if not is_production():
        logger.info("[env-guard] GitHub remove_deploy_key %s/%s/%s skipped (env=%s)", owner, repo, key_id, env_name())
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.delete(
                f"https://api.github.com/repos/{owner}/{repo}/keys/{key_id}",
                headers={
                    "Authorization": f"Bearer {user_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        return r.status_code in (204, 404)
    except Exception as e:
        logger.warning("remove_github_deploy_key failed: %s", e)
        return False


def github_ssh_url(repo_url: str) -> Optional[str]:
    """Turn https://github.com/owner/repo(.git) into git@github.com:owner/repo.git"""
    m = re.match(
        r"^https?://(?:[^@]+@)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        (repo_url or "").strip(),
    )
    if not m:
        return None
    return f"git@github.com:{m.group(1)}/{m.group(2)}.git"
