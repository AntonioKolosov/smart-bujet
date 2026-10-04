from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class CreditAccountCreate(BaseModel):
    name: str = Field(..., max_length=128)
    bank_name: str | None = Field(None, max_length=128)
    original_amount: Decimal = Field(..., gt=0)
    currency: str = Field("KZT", max_length=3)
    interest_rate: Decimal | None = Field(None, ge=0)
    monthly_payment: Decimal | None = Field(None, ge=0)


class CreditAccountRepay(BaseModel):
    amount: Decimal = Field(..., gt=0)


class CreditAccountRead(BaseModel):
    id: uuid.UUID
    user_id: int
    name: str
    bank_name: str | None = None
    original_amount: float
    remaining_amount: float
    currency: str
    interest_rate: float | None = None
    monthly_payment: float | None = None
    is_active: bool
    closed_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CreditSummaryResponse(BaseModel):
    total_debt: float
    total_monthly_payment: float
    active_credits_count: int
    closed_credits_count: int
    credits_count: int
