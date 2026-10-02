from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.category import CategoryRead, CategoryCreate
from src.models.user import User
from src.models.category import Category, CategoryType
from src.services.category_service import CategoryService

router = APIRouter()

@router.get("/", response_model=List[CategoryRead])
async def list_categories(
    type: Optional[str] = Query(None, description="Filter by type: income or expense"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = CategoryService(session)
    cat_type = CategoryType(type) if type in CategoryType._value2member_map_ else None
    return await service.get_categories(user_id=current_user.id, cat_type=cat_type)

@router.post("/", response_model=CategoryRead)
async def create_category(
    data: CategoryCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    category = Category(
        name=data.name.strip(),
        type=CategoryType(data.type),
        user_id=current_user.id,
        is_system=False
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category

