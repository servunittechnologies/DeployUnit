"""GitHub helpers used outside the OAuth-scoped router."""
import re
import logging
import httpx
from typing import Optional

from db import get_db
from crypto_utils import decrypt_token

logger = logging.getLogger(__name__)


def parse_repo(repo_url: str) -> tuple[str, str] | None:
    if not repo_url:
        return None
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo_url.strip())
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", repo_url.strip())
    if m:
        return m.group(1), m.group(2)
    return None


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
