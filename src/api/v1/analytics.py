from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.analytics import ReportResponse
from src.models.user import User
from src.services.report_service import ReportService

router = APIRouter()

@router.get("/report", response_model=ReportResponse)
async def get_report(
    period: str = Query("month", description="Period: week, month, year"),
    include_family: bool = Query(False, description="Include family group transactions"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ReportService(session)
    family_id = current_user.family_group_id if include_family else None
    summary = await service.get_summary(
        user_id=current_user.id,
        family_group_id=family_id,
        period=period
    )
    return ReportResponse(
        total_expenses=f"{summary['total_expense']:.2f}",
        total_income=f"{summary['total_income']:.2f}",
        currency=current_user.currency or "RUB",
        details={
            "period": summary["period"],
            "balance": summary["balance"],
            "categories": summary["categories"]
        }
    )

