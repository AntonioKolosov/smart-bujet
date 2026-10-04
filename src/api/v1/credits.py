from __future__ import annotations

import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import get_current_user
from src.models.user import User
from src.schemas.credit import CreditAccountCreate, CreditAccountRepay, CreditAccountRead, CreditSummaryResponse
from src.services.credit_service import CreditService

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/", response_model=list[CreditAccountRead])
async def list_credits(
    active_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve current user's personal credits (strictly isolated from family)."""
    service = CreditService(db)
    credits = await service.get_user_credits(current_user.id, active_only=active_only)
    return credits


@router.get("/summary", response_model=CreditSummaryResponse)
async def get_credits_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve aggregated debt metrics for current user."""
    service = CreditService(db)
    return await service.get_credit_summary(current_user.id)


@router.post("/", response_model=CreditAccountRead, status_code=status.HTTP_201_CREATED)
async def create_credit(
    payload: CreditAccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new personal credit/loan."""
    service = CreditService(db)
    credit = await service.create_credit(
        user_id=current_user.id,
        name=payload.name,
        original_amount=payload.original_amount,
        currency=payload.currency or current_user.currency or "KZT",
        bank_name=payload.bank_name,
        interest_rate=payload.interest_rate,
        monthly_payment=payload.monthly_payment,
    )
    return credit


@router.post("/{credit_id}/repay", response_model=CreditAccountRead)
async def repay_credit(
    credit_id: uuid.UUID,
    payload: CreditAccountRepay,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Repay part or all of a credit/loan."""
    service = CreditService(db)
    credit, was_closed = await service.repay_credit(
        user_id=current_user.id,
        credit_id=credit_id,
        amount=payload.amount
    )
    if not credit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit account not found"
        )
    return credit


@router.delete("/{credit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credit(
    credit_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete or archive a credit."""
    service = CreditService(db)
    success = await service.delete_credit(credit_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit account not found"
        )
    return None
