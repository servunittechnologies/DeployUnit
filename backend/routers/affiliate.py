import logging
import secrets
from fastapi import APIRouter, HTTPException, Request
from db import get_db
from auth_utils import get_current_user

router = APIRouter(prefix="/affiliate", tags=["affiliate"])
logger = logging.getLogger(__name__)

def _generate_ref_code():
    return secrets.token_hex(4)

@router.get("/stats")
async def get_affiliate_stats(request: Request):
    user = await get_current_user(request)
    db = get_db()
    # ... (Affiliate stats implementation)