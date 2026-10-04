from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Numeric, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.transaction import Transaction


class CreditAccount(Base, TimestampMixin):
    __tablename__ = "credit_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    bank_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    remaining_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="KZT")
    interest_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    monthly_payment: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", backref="credit_accounts")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="credit_account")
