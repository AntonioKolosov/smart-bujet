from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.deps import get_db, get_current_user
from src.schemas.analytics import ReportResponse
from src.models.user import User

router = APIRouter()

@router.get("/report", response_model=ReportResponse)
async def get_report(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # TODO: stub
    return ReportResponse(total_expenses="0", total_income="0", currency="KZT")
