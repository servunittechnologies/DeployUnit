"""Mock GitHub repo browser — until real OAuth is wired."""
from fastapi import APIRouter, Request
from pydantic import BaseModel
from auth_utils import get_current_user

router = APIRouter(prefix="/github", tags=["github"])


SAMPLE_REPOS = [
    {"id": "1", "name": "novabrew/web", "framework": "nextjs", "default_branch": "main",
     "url": "https://github.com/vercel/next.js"},
    {"id": "2", "name": "novabrew/api", "framework": "node", "default_branch": "main",
     "url": "https://github.com/expressjs/express"},
    {"id": "3", "name": "novabrew/admin", "framework": "nextjs", "default_branch": "develop",
     "url": "https://github.com/shadcn-ui/ui"},
    {"id": "4", "name": "novabrew/billing-worker", "framework": "node", "default_branch": "main",
     "url": "https://github.com/nestjs/nest"},
    {"id": "5", "name": "novabrew/landing", "framework": "nextjs", "default_branch": "main",
     "url": "https://github.com/vercel/commerce"},
]


class ConnectIn(BaseModel):
    workspace_id: str


@router.get("/repos")
async def list_repos(request: Request):
    await get_current_user(request)
    return SAMPLE_REPOS


@router.post("/connect")
async def connect_github(payload: ConnectIn, request: Request):
    await get_current_user(request)
    # Mock — pretend we stored an installation_id for this workspace.
    return {"connected": True, "workspace_id": payload.workspace_id, "username": "deployunit-mock"}
