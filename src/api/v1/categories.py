from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.category import CategoryRead
from src.models.user import User

router = APIRouter()

@router.get("/", response_model=List[CategoryRead])
async def list_categories(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: list system + user categories
    return []
