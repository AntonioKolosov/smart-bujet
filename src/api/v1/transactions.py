from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.transaction import TransactionRead, TransactionCreate
from src.models.user import User

router = APIRouter()

@router.get("/", response_model=List[TransactionRead])
async def list_transactions(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: stub
    return []

@router.post("/", response_model=TransactionRead)
async def create_transaction(
    data: TransactionCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: stub
    pass
