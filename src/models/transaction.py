from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Numeric, String, Text, BigInteger, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base, TimestampMixin
from src.models.category import CategoryType

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.family import FamilyGroup
    from src.models.category import Category
    from src.models.asset import AssetAccount


class TransactionSource(str, Enum):
    text = "text"
    voice = "voice"
    photo = "photo"
    manual = "manual"


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    family_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("family_groups.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    original_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    discount_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    type: Mapped[CategoryType] = mapped_column()
    asset_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("asset_accounts.id"), nullable=True)
    asset_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    exchange_rate: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    related_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    item_name: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str | None] = mapped_column(Text)
    source: Mapped[TransactionSource] = mapped_column()
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="transactions")
    family_group: Mapped["FamilyGroup" | None] = relationship("FamilyGroup", back_populates="transactions")
    category: Mapped["Category"] = relationship("Category", back_populates="transactions")
    asset_account: Mapped["AssetAccount" | None] = relationship("AssetAccount", back_populates="transactions")
    related_transaction: Mapped["Transaction" | None] = relationship("Transaction", remote_side="Transaction.id", foreign_keys=[related_transaction_id], post_update=True)

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category else None
