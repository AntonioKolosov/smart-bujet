import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_current_user
from src.models.user import User
from src.services.family_service import FamilyService
from src.schemas.family import FamilySummaryResponse, FamilyTransactionItem
from src.bot.bot import bot

logger = logging.getLogger(__name__)
router = APIRouter()


class JoinFamilyRequest(BaseModel):
    invite_code: str


@router.get("/summary", response_model=FamilySummaryResponse)
async def get_family_summary(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = FamilyService(session)
    return await service.get_family_summary(current_user)


@router.get("/transactions", response_model=list[FamilyTransactionItem])
async def get_family_transactions(
    limit: int = Query(60, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = FamilyService(session)
    return await service.get_family_transactions(current_user, limit=limit, offset=offset)


@router.post("/join")
async def join_family_group(
    data: JoinFamilyRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = FamilyService(session)
    group, partner_id, msg = await service.join_by_invite(current_user, data.invite_code)
    if not group:
        status_code = status.HTTP_400_BAD_REQUEST if "уже состоите" in msg else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=msg)

    if partner_id:
        try:
            author_title = current_user.first_name or (f"@{current_user.username}" if current_user.username else "Партнёр")
            await bot.send_message(
                partner_id,
                f"🎉 <b>{author_title}</b> присоединился(лась) к вашей семейной группе <b>«{group.name}»</b>!\n"
                f"Теперь ваши расходы и доходы синхронизированы в MiniApp."
            )
        except Exception:
            logger.exception("Failed to notify partner on join")

    return {"success": True, "message": msg, "group_name": group.name}


@router.post("/leave")
async def leave_family_group(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = FamilyService(session)
    success, partner_id = await service.leave_group(current_user)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вы не состоите в семейной группе")

    if partner_id:
        try:
            author_title = current_user.first_name or (f"@{current_user.username}" if current_user.username else "Партнёр")
            await bot.send_message(
                partner_id,
                f"ℹ️ <b>{author_title}</b> покинул(а) семейную группу.\n"
                f"Семейный бюджет больше не синхронизируется."
            )
        except Exception:
            logger.exception("Failed to notify partner on leave")

    return {"success": True}
