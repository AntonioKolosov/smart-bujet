from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from src.models.category import CategoryType

class TransactionCreate(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0"), description="Сумма должна быть строго больше 0")
    category_id: int
    item_name: str | None = None
    type: str = "expense"
    raw_text: str | None = None
    source: str = "manual"
    transaction_date: datetime | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid_types = {t.value for t in CategoryType}
        if v not in valid_types:
            raise ValueError(f"Недопустимый тип операции: {v}")
        return v

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
    asset_account_id: UUID | None = None
    asset_amount: Decimal | None = None
    exchange_rate: Decimal | None = None
    asset_currency: str | None = None
    item_name: str | None = None
    raw_text: str | None = None
    source: str
    transaction_date: datetime

    model_config = ConfigDict(from_attributes=True)

