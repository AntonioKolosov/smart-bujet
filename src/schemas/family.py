from datetime import datetime
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
    first_name: str | None = None
    username: str | None = None
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
    invite_code: str | None = None
    invite_link: str | None = None
    member_count: int
    combined_balance: float
    combined_month_expense: float
    combined_month_income: float
    currency: str
    month_period_name: str
    members: list[FamilyMemberInfo]

    model_config = ConfigDict(from_attributes=True)


class FamilyTransactionItem(BaseModel):
    id: UUID
    user_id: int
    author_name: str
    author_username: str | None = None
    is_current_user: bool
    amount: float
    original_amount: float | None = None
    discount_amount: float | None = None
    type: str
    category_id: int | None = None
    category_name: str | None = None
    item_name: str | None = None
    raw_text: str | None = None
    source: str
    transaction_date: datetime

    model_config = ConfigDict(from_attributes=True)
