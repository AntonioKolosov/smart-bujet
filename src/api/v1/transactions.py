import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, desc, or_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.transaction import TransactionRead, TransactionCreate, TransactionUpdate
from src.services.transaction_service import TransactionService
from src.models.user import User
from src.models.transaction import Transaction, TransactionSource
from src.models.category import CategoryType

router = APIRouter()

@router.get("/", response_model=List[TransactionRead])
async def list_transactions(
    include_family: bool = Query(False, description="Include family group transactions"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conditions = [Transaction.user_id == current_user.id]
    if include_family and current_user.family_group_id:
        conditions = [or_(
            Transaction.user_id == current_user.id,
            Transaction.family_group_id == current_user.family_group_id
        )]

    query = (
        select(Transaction)
        .options(joinedload(Transaction.category))
        .where(*conditions)
        .order_by(desc(Transaction.transaction_date))
        .offset(offset)
        .limit(limit)
    )
    result = await session.scalars(query)
    return result.all()

@router.post("/", response_model=TransactionRead)
async def create_transaction(
    data: TransactionCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tx = Transaction(
        user_id=current_user.id,
        family_group_id=current_user.family_group_id,
        category_id=data.category_id,
        amount=float(data.amount),
        type=CategoryType(data.type),
        item_name=data.item_name,
        raw_text=data.raw_text,
        source=TransactionSource(data.source) if data.source in TransactionSource._value2member_map_ else TransactionSource.manual
    )
    if data.transaction_date:
        tx.transaction_date = data.transaction_date

    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx

@router.patch("/{tx_id}", response_model=TransactionRead)
async def update_transaction(
    tx_id: uuid.UUID,
    data: TransactionUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TransactionService(session)
    return await service.update_transaction(
        user_id=current_user.id,
        tx_id=tx_id,
        data=data
    )

@router.delete("/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    tx_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = TransactionService(session)
    await service.delete_transaction(
        user_id=current_user.id,
        tx_id=tx_id
    )
    return None


