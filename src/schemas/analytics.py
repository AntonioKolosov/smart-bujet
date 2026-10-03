from pydantic import BaseModel
from typing import Any

class ReportResponse(BaseModel):
    total_expenses: str
    total_income: str
    currency: str
    details: dict[str, Any] = {}
