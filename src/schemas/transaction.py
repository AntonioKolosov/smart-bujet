from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from datetime import datetime
from uuid import UUID

class TransactionCreate(BaseModel):
    amount: Decimal
    category_id: int
    item_name: str | None = None
    type: str = "expense"
    raw_text: str | None = None
    source: str = "manual"
    transaction_date: datetime | None = None

class TransactionRead(BaseModel):
    id: UUID
    user_id: int
    family_group_id: UUID | None = None
    category_id: int
    category_name: str | None = None
    amount: Decimal
    original_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    type: str
    item_name: str | None = None
    raw_text: str | None = None
    source: str
    transaction_date: datetime

    model_config = ConfigDict(from_attributes=True)

