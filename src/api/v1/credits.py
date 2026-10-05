from __future__ import annotations

import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.models.user import User
from src.models.credit import CreditAccount
from src.models.category import Category, CategoryType
from src.models.transaction import Transaction, TransactionSource
from src.schemas.credit import CreditAccountCreate, CreditAccountRepay, CreditAccountRead, CreditSummaryResponse
from src.services.credit_service import CreditService
from src.services.category_service import CategoryService

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
    """Repay part or all of a credit/loan and atomically record ledger expense."""
    if current_user.initial_balance is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сначала установите начальный баланс в боте"
        )

    if payload.amount <= Decimal("0.0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сумма погашения должна быть строго больше нуля"
        )

    # Pessimistic lock on credit account
    query = (
        select(CreditAccount)
        .where(CreditAccount.id == credit_id, CreditAccount.user_id == current_user.id)
        .with_for_update()
    )
    credit = await db.scalar(query)
    if not credit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Кредитный счет не найден"
        )

    curr_remaining = Decimal(str(credit.remaining_amount or 0))
    if not credit.is_active or curr_remaining <= Decimal("0.0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Кредит уже полностью погашен"
        )

    # 1. Deduct remaining amount
    new_remaining = max(Decimal("0.0"), curr_remaining - payload.amount)
    credit.remaining_amount = new_remaining
    if credit.is_active and new_remaining <= Decimal("0.0"):
        credit.is_active = False
        credit.closed_at = func.now()

    # 2. Category lookup or creation
    cat_service = CategoryService(db)
    repay_cat = await cat_service.find_by_name("Погашение кредита", CategoryType.expense, current_user.id)
    if not repay_cat:
        repay_cat = Category(name="Погашение кредита", type=CategoryType.expense, is_system=True)
        db.add(repay_cat)
        await db.flush()

    # 3. Create expense transaction in ledger
    tx = Transaction(
        user_id=current_user.id,
        family_group_id=current_user.family_group_id,
        category_id=repay_cat.id,
        credit_account_id=credit.id,
        amount=float(payload.amount),
        type=CategoryType.expense,
        item_name=f"Погашение: {credit.name}",
        source=TransactionSource.manual,
        transaction_date=func.now()
    )
    db.add(tx)

    # 4. Atomic commit
    await db.commit()
    await db.refresh(credit)
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
