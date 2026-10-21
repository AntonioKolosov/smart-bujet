import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_current_user
from src.models.user import User
from src.models.agent_memory import UserAgentMemory, FactCategory
from src.schemas.facts import FactCreateRequest, FactUpdateRequest, FactResponse
from src.services.ai_service import AIService

router = APIRouter()

CATEGORY_META = {
    FactCategory.goal.value: {"label": "Цель", "badge": "🎯 Цель"},
    FactCategory.habit.value: {"label": "Привычка", "badge": "🔄 Привычка"},
    FactCategory.schedule.value: {"label": "Расписание", "badge": "📅 Расписание"},
    FactCategory.constraint.value: {"label": "Ограничение", "badge": "⛔ Ограничение"},
    FactCategory.other.value: {"label": "Заметка", "badge": "💡 Заметка"},
}


def _to_response(fact: UserAgentMemory) -> FactResponse:
    cat_val = fact.category if isinstance(fact.category, str) else fact.category.value
    meta = CATEGORY_META.get(cat_val, {"label": "Заметка", "badge": "💡 Заметка"})
    return FactResponse(
        id=fact.id,
        user_id=fact.user_id,
        category=cat_val,
        category_label=meta["label"],
        category_badge=meta["badge"],
        fact_text=fact.fact_text,
        is_active=fact.is_active,
        created_at=fact.created_at,
        updated_at=fact.updated_at,
    )


@router.get("/", response_model=list[FactResponse])
async def list_facts(
    is_active: bool = Query(True, description="Filter active/archived facts"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(UserAgentMemory)
        .where(
            UserAgentMemory.user_id == current_user.id,
            UserAgentMemory.is_active == is_active,
        )
        .order_by(UserAgentMemory.created_at.desc())
    )
    facts = (await session.scalars(stmt)).all()
    return [_to_response(f) for f in facts]


@router.post("/", response_model=FactResponse, status_code=status.HTTP_201_CREATED)
async def create_fact(
    payload: FactCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clean_text = payload.fact_text.strip()
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Текст факта не может быть пустым",
        )

    cat = payload.category
    valid_cats = {c.value for c in FactCategory}
    if not cat or cat not in valid_cats:
        ai_service = AIService()
        ai_res = await ai_service.classify_user_fact(clean_text)
        cat = ai_res.get("category", FactCategory.other.value)
        if cat not in valid_cats:
            cat = FactCategory.other.value

    fact = UserAgentMemory(
        user_id=current_user.id,
        category=cat,
        fact_text=clean_text,
        is_active=True,
    )
    session.add(fact)
    await session.commit()
    await session.refresh(fact)
    return _to_response(fact)


@router.patch("/{fact_id}", response_model=FactResponse)
async def update_fact(
    fact_id: uuid.UUID,
    payload: FactUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fact = await session.get(UserAgentMemory, fact_id)
    if not fact or fact.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Факт не найден")

    if payload.fact_text is not None:
        clean = payload.fact_text.strip()
        if not clean:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Текст факта не может быть пустым",
            )
        fact.fact_text = clean

    if payload.category is not None:
        valid_cats = {c.value for c in FactCategory}
        if payload.category in valid_cats:
            fact.category = payload.category

    if payload.is_active is not None:
        fact.is_active = payload.is_active

    await session.commit()
    await session.refresh(fact)
    return _to_response(fact)


@router.delete("/{fact_id}", status_code=status.HTTP_200_OK)
async def delete_fact(
    fact_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fact = await session.get(UserAgentMemory, fact_id)
    if not fact or fact.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Факт не найден")

    await session.delete(fact)
    await session.commit()
    return {"status": "ok", "deleted_id": str(fact_id)}
