from pydantic import BaseModel, ConfigDict, model_validator
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

class TransactionUpdate(BaseModel):
    amount: Decimal | None = None
    category_id: int | None = None
    item_name: str | None = None

    @model_validator(mode="after")
    def check_at_least_one_field(self) -> "TransactionUpdate":
        if self.amount is None and self.category_id is None and self.item_name is None:
            raise ValueError("Необходимо передать хотя бы одно поле для обновления")
        if self.amount is not None and self.amount <= Decimal("0"):
            raise ValueError("Сумма должна быть строго больше 0")
        return self

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

