from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.family import FamilyGroupRead, FamilyGroupCreate
from src.models.user import User

router = APIRouter()

@router.get("/", response_model=list[FamilyGroupRead])
async def list_family_groups(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: stub
    return []

@router.post("/", response_model=FamilyGroupRead)
async def create_family_group(
    data: FamilyGroupCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: stub
    pass
