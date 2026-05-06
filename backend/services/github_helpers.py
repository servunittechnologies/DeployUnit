"""GitHub helpers used outside the OAuth-scoped router."""
import re
import logging
import urllib.parse
import httpx
from typing import Optional

from db import get_db
from crypto_utils import decrypt_token

logger = logging.getLogger(__name__)


def parse_repo(repo_url: str) -> tuple[str, str] | None:
    if not repo_url:
        return None
    m = re.match(r"^https?://(?:[^@]+@)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url.strip())
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", repo_url.strip())
    if m:
        return m.group(1), m.group(2)
    return None


def is_github_https(repo_url: str) -> bool:
    return bool(repo_url) and re.match(r"^https?://(?:[^@]+@)?github\.com/", repo_url.strip()) is not None


def strip_token_from_url(repo_url: str) -> str:
    """Return the repo URL with any embedded credentials removed (for logs)."""
    if not repo_url:
        return repo_url
    return re.sub(r"https?://[^@]+@", "https://", repo_url)


def inject_github_token(repo_url: str, token: str) -> str:
    """Rewrite https://github.com/... to https://x-access-token:TOKEN@github.com/...

    Leaves non-GitHub or already-authenticated URLs untouched.
    """
    if not repo_url or not token:
        return repo_url
    if not is_github_https(repo_url):
        return repo_url
    # If URL already has a userinfo part, strip it and re-inject.
    base = re.sub(r"^https?://[^@]+@", "https://", repo_url.strip())
    encoded = urllib.parse.quote(token, safe="")
    return base.replace("https://github.com/", f"https://x-access-token:{encoded}@github.com/", 1)


async def _user_token(user_id: str) -> Optional[str]:
    if not user_id:
        return None
    db = get_db()
    full = await db.users.find_one({"id": user_id}, {"_id": 0})
    enc = (full or {}).get("github_access_token")
    if not enc:
        return None
    try:
        return decrypt_token(enc)
    except Exception:
        return None


async def workspace_github_token(workspace_id: str) -> Optional[str]:
    """Return the first available GitHub token for the workspace, preferring
    the owner. Any member with a linked GitHub account is acceptable as a
    fallback — needed for agencies where a non-owner developer linked GitHub.
    """
    if not workspace_id:
        return None
    db = get_db()
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    if not ws:
        return None
    # Try owner first
    owner_id = ws.get("owner_id") or ws.get("owner")
    if owner_id:
        t = await _user_token(owner_id)
        if t:
            return t
    # Then any member
    for m in (ws.get("members") or []):
        uid = m.get("user_id") if isinstance(m, dict) else m
        if uid and uid != owner_id:
            t = await _user_token(uid)
            if t:
                return t
    return None


async def detect_default_branch(repo_url: str, *, user_id: Optional[str] = None) -> Optional[str]:
    """Best-effort: query GitHub for the repo's default branch.
    Falls back to None when repo isn't on GitHub or call fails — caller decides what to do."""
    parsed = parse_repo(repo_url)
    if not parsed:
        return None
    owner, repo = parsed
    token = await _user_token(user_id) if user_id else None
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
        if r.status_code == 200:
            return (r.json() or {}).get("default_branch")
        if r.status_code == 404:
            logger.info("github default-branch lookup 404 for %s/%s (private without token?)", owner, repo)
        else:
            logger.info("github default-branch lookup %s for %s/%s", r.status_code, owner, repo)
    except Exception as e:
        logger.warning("github default-branch lookup failed: %s", e)
    return None


async def probe_repo_visibility(repo_url: str) -> Optional[str]:
    """Return 'public', 'private', or None if we can't tell (network issue or non-GitHub).
    No auth used — a 404 without a token strongly suggests 'private' (or the repo
    doesn't exist). 200 means public.
    """
    parsed = parse_repo(repo_url)
    if not parsed:
        return None
    owner, repo = parsed
    try:
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get(f"https://api.github.com/repos/{owner}/{repo}")
        if r.status_code == 200:
            return "public"
        if r.status_code == 404:
            return "private"
    except Exception:
        return None
    return None
