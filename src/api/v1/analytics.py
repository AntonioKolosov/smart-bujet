from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.analytics import ReportResponse, CategoryAnalyticsResponse, MonthlyAnalyticsResponse
from src.models.user import User
from src.services.report_service import ReportService

router = APIRouter()


async def _verify_family_access(user: User, session: AsyncSession) -> UUID:
    """Ensure user belongs to an active family group with at least 2 members."""
    if not user.family_group_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы не состоите в семейной группе"
        )
    count = await session.scalar(
        select(func.count(User.id)).where(User.family_group_id == user.family_group_id)
    )
    if (count or 0) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы не состоите в семейной группе"
        )
    return user.family_group_id


@router.get("/report", response_model=ReportResponse)
async def get_report(
    period: str = Query("month", description="Period: week, month, year"),
    include_family: bool = Query(False, description="Include family group transactions"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ReportService(session)
    family_id = None
    if include_family:
        family_id = await _verify_family_access(current_user, session)
    summary = await service.get_summary(
        user_id=current_user.id,
        family_group_id=family_id,
        period=period
    )
    return ReportResponse(
        total_expenses=f"{summary['total_expense']:.2f}",
        total_income=f"{summary['total_income']:.2f}",
        currency=current_user.currency or "KZT",
        details={
            "period": summary["period"],
            "balance": summary["balance"],
            "categories": summary["categories"]
        }
    )


@router.get("/categories", response_model=CategoryAnalyticsResponse)
async def get_categories_analytics(
    family: bool = Query(False, description="Family mode analytics"),
    period: str = Query("month", description="Period: month, year"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ReportService(session)
    family_id = None
    if family:
        family_id = await _verify_family_access(current_user, session)
    data = await service.get_category_breakdown(
        user_id=current_user.id,
        family_group_id=family_id,
        period=period
    )
    data["currency"] = current_user.currency or "KZT"
    return data


@router.get("/monthly", response_model=MonthlyAnalyticsResponse)
async def get_monthly_analytics(
    family: bool = Query(False, description="Family mode analytics"),
    months: int = Query(6, ge=1, le=24, description="Number of months to trend"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ReportService(session)
    family_id = None
    if family:
        family_id = await _verify_family_access(current_user, session)
    data = await service.get_monthly_dynamics(
        user_id=current_user.id,
        family_group_id=family_id,
        months_count=months
    )
    data["currency"] = current_user.currency or "KZT"
    return data


