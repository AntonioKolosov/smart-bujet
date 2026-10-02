from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.transaction import TransactionRead, TransactionCreate
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

