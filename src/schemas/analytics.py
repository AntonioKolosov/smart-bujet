from pydantic import BaseModel
from typing import Dict, Any

class ReportResponse(BaseModel):
    total_expenses: str
    total_income: str
    currency: str
    details: Dict[str, Any] = {}
