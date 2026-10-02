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


from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_current_user, get_db
from src.models.user import User
from src.services.transaction_service import TransactionService

@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    tx_service = TransactionService(session)
    bal_data = await tx_service.get_user_balance(current_user.id)
    return {
        "id": current_user.id,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "currency": current_user.currency,
        "initial_balance": bal_data["initial_balance"],
        "total_income": bal_data["total_income"],
        "total_expense": bal_data["total_expense"],
        "month_income": bal_data.get("month_income", 0.0),
        "month_expense": bal_data.get("month_expense", 0.0),
        "month_period_name": bal_data.get("month_period_name", "Текущий месяц"),
        "current_balance": bal_data["current_balance"],
        "family_group_id": str(current_user.family_group_id) if current_user.family_group_id else None
    }

