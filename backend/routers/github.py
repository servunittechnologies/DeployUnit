"""GitHub repos endpoint — real GitHub API when user has linked, otherwise sample fallback."""
import logging
import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from db import get_db
from auth_utils import get_current_user
from crypto_utils import decrypt_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/github", tags=["github"])


SAMPLE_REPOS = [
    {"id": "1", "name": "novabrew/web", "framework": "nextjs", "default_branch": "main",
     "url": "https://github.com/vercel/next.js", "private": False, "is_sample": True},
    {"id": "2", "name": "novabrew/api", "framework": "node", "default_branch": "main",
     "url": "https://github.com/expressjs/express", "private": False, "is_sample": True},
    {"id": "3", "name": "novabrew/admin", "framework": "nextjs", "default_branch": "develop",
     "url": "https://github.com/shadcn-ui/ui", "private": False, "is_sample": True},
    {"id": "4", "name": "novabrew/billing-worker", "framework": "node", "default_branch": "main",
     "url": "https://github.com/nestjs/nest", "private": False, "is_sample": True},
    {"id": "5", "name": "novabrew/landing", "framework": "nextjs", "default_branch": "main",
     "url": "https://github.com/vercel/commerce", "private": False, "is_sample": True},
]


def _detect_framework(language: str | None, name: str) -> str:
    lang = (language or "").lower()
    n = name.lower()
    if any(x in n for x in ["next", "nuxt", "site", "web", "landing"]):
        return "nextjs"
    if lang in ("javascript", "typescript"):
        return "nextjs"  # Default for JS/TS — usually Next.js or static
    if lang in ("python", "go", "ruby", "rust", "java"):
        return "node"
    if lang in ("html", "css"):
        return "static"
    return "nextjs"


class ConnectIn(BaseModel):
    workspace_id: str


@router.get("/repos")
async def list_repos(request: Request):
    user = await get_current_user(request)
    db = get_db()
    full = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    enc = (full or {}).get("github_access_token")
    if not enc:
        return SAMPLE_REPOS

    try:
        token = decrypt_token(enc)
    except Exception:
        logger.warning("could not decrypt github token; falling back")
        return SAMPLE_REPOS

    repos: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.get(
                "https://api.github.com/user/repos",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                params={"per_page": 50, "sort": "updated", "direction": "desc", "type": "all"},
            )
        if r.status_code == 401:
            # Token revoked — clear it
            await db.users.update_one({"id": user["id"]}, {"$unset": {"github_access_token": ""}})
            return SAMPLE_REPOS
        if r.status_code != 200:
            logger.warning("github repos %s %s", r.status_code, r.text[:200])
            return SAMPLE_REPOS
        for repo in r.json():
            repos.append({
                "id": str(repo["id"]),
                "name": repo["full_name"],
                "framework": _detect_framework(repo.get("language"), repo["name"]),
                "default_branch": repo.get("default_branch") or "main",
                "url": repo.get("clone_url") or repo.get("html_url"),
                "private": bool(repo.get("private")),
                "is_sample": False,
            })
    except Exception as e:
        logger.warning("github fetch failed: %s", e)
        return SAMPLE_REPOS

    return repos or SAMPLE_REPOS


@router.post("/connect")
async def connect_github(payload: ConnectIn, request: Request):
    """Compatibility shim — real connection now flows via /api/auth/github/start?link=true."""
    user = await get_current_user(request)  # auth-required gate
    _ = user
    return {
        "connected": False,
        "workspace_id": payload.workspace_id,
        "message": "Use /api/auth/github/start?link=true to begin OAuth.",
    }
