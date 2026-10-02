from pydantic import BaseModel, ConfigDict
from typing import Optional
from decimal import Decimal
from datetime import datetime
from uuid import UUID

class TransactionCreate(BaseModel):
    amount: Decimal
    category_id: int
    item_name: Optional[str] = None
    type: str = "expense"
    raw_text: Optional[str] = None
    source: str = "manual"
    transaction_date: Optional[datetime] = None

class TransactionRead(BaseModel):
    id: UUID
    user_id: int
    family_group_id: Optional[UUID] = None
    category_id: int
    category_name: Optional[str] = None
    amount: Decimal
    original_amount: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    type: str
    item_name: Optional[str] = None
    raw_text: Optional[str] = None
    source: str
    transaction_date: datetime

    model_config = ConfigDict(from_attributes=True)

