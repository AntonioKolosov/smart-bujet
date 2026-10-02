from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class FamilyGroupCreate(BaseModel):
    name: str


class FamilyGroupRead(BaseModel):
    id: UUID
    name: str
    owner_id: int
    invite_code: str

    model_config = ConfigDict(from_attributes=True)


class FamilyMemberInfo(BaseModel):
    id: int
    first_name: Optional[str] = None
    username: Optional[str] = None
    currency: str = "KZT"
    current_balance: float = 0.0
    month_expense: float = 0.0
    month_income: float = 0.0
    is_owner: bool = False
    is_current_user: bool = False

    model_config = ConfigDict(from_attributes=True)


class FamilySummaryResponse(BaseModel):
    group_id: UUID
    name: str
    status: str  # "single_member" | "active_family"
    is_owner: bool
    invite_code: Optional[str] = None
    invite_link: Optional[str] = None
    member_count: int
    combined_balance: float
    combined_month_expense: float
    combined_month_income: float
    currency: str
    month_period_name: str
    members: List[FamilyMemberInfo]

    model_config = ConfigDict(from_attributes=True)


class FamilyTransactionItem(BaseModel):
    id: UUID
    user_id: int
    author_name: str
    author_username: Optional[str] = None
    is_current_user: bool
    amount: float
    original_amount: Optional[float] = None
    discount_amount: Optional[float] = None
    type: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    item_name: Optional[str] = None
    raw_text: Optional[str] = None
    source: str
    transaction_date: datetime

    model_config = ConfigDict(from_attributes=True)
