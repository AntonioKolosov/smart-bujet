from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.family import FamilyGroupRead, FamilyGroupCreate
from src.models.user import User
from src.models.family import FamilyGroup
from src.services.family_service import FamilyService

router = APIRouter()

class JoinFamilyRequest(BaseModel):
    invite_code: str

@router.get("/current", response_model=Optional[FamilyGroupRead])
async def get_current_family_group(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.family_group_id:
        return None
    return await session.get(FamilyGroup, current_user.family_group_id)

@router.post("/", response_model=FamilyGroupRead)
async def create_family_group(
    data: FamilyGroupCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = FamilyService(session)
    return await service.create_group(owner_id=current_user.id, name=data.name)

@router.post("/join", response_model=FamilyGroupRead)
async def join_family_group(
    data: JoinFamilyRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = FamilyService(session)
    group = await service.join_group(user_id=current_user.id, invite_code=data.invite_code)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family group not found with this invite code"
        )
    return group

@router.post("/leave")
async def leave_family_group(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = FamilyService(session)
    success = await service.leave_group(user_id=current_user.id)
    return {"success": success}

