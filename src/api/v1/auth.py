import json
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from src.core.config import settings
from src.core.security import validate_init_data

router = APIRouter()

class ValidateInitDataRequest(BaseModel):
    initData: str

@router.post("/validate")
async def validate_auth(data: ValidateInitDataRequest):
    validated = validate_init_data(data.initData, settings.bot_token)
    if not validated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired initData signature"
        )

    user_info = {}
    if "user" in validated:
        try:
            user_info = json.loads(validated["user"])
        except Exception:
            pass

    return {
        "status": "ok",
        "valid": True,
        "user": user_info
    }

