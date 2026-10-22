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
    bal_data = await tx_service.get_user_balance(current_user.id, user=current_user)
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


class UpdateCurrencyRequest(BaseModel):
    currency: str


@router.patch("/me/currency")
async def update_my_currency(
    data: UpdateCurrencyRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    cur = data.currency.upper().strip()
    if cur not in {"KZT", "RUB", "USD", "EUR"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поддерживаемые валюты: KZT, RUB, USD, EUR"
        )
    current_user.currency = cur
    await session.commit()
    return {"status": "ok", "currency": cur}



from sqlalchemy import select
from src.models.family import FamilyGroup

@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Permanently erases user account and all personal/financial data via ON DELETE CASCADE.
    If user owns a family group, group is dissociated or transferred.
    """
    if current_user.family_group_id:
        family = await session.get(FamilyGroup, current_user.family_group_id)
        if family and family.owner_id == current_user.id:
            other_member = await session.scalar(
                select(User).where(User.family_group_id == family.id, User.id != current_user.id)
            )
            if other_member:
                family.owner_id = other_member.id
                current_user.family_group_id = None
                await session.flush()
            else:
                current_user.family_group_id = None
                await session.flush()
                await session.delete(family)
                await session.flush()
        else:
            current_user.family_group_id = None
            await session.flush()

    await session.delete(current_user)
    await session.commit()
    return {"status": "ok", "message": "Все данные профиля безвозвратно удалены."}


