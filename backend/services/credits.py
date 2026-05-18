import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import HTTPException
from db import get_db
from services.plans import user_plan

logger = logging.getLogger(__name__)

def grant_credits(user_id: str, amount: int, reason: str, type_: str = 'topup', ref_id: Optional[str] = None, ref_type: Optional[str] = None) -> int:
    # Credits service implementation...
    return 1000 # Placeholder for brevity in tool call