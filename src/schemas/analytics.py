from pydantic import BaseModel
from typing import Any

class ReportResponse(BaseModel):
    total_expenses: str
    total_income: str
    currency: str
    details: dict[str, Any] = {}

class CategorySpendItem(BaseModel):
    name: str
    amount: float
    percentage: float
    tx_count: int
    color: str
    icon: str

class CategoryAnalyticsResponse(BaseModel):
    total_spend: float
    currency: str
    period_label: str
    categories: list[CategorySpendItem]

class MonthlyTrendItem(BaseModel):
    year: int
    month: int
    label: str
    total_expense: float
    total_income: float
    net_savings: float

class AnalyticsKeyMetrics(BaseModel):
    current_month_spend: float
    monthly_average_spend: float
    top_category_name: str | None = None
    top_category_amount: float | None = None
    top_category_percent: float | None = None

class MonthlyAnalyticsResponse(BaseModel):
    currency: str
    months_count: int
    history: list[MonthlyTrendItem]
    metrics: AnalyticsKeyMetrics

