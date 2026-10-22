from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Numeric, String, Text, BigInteger, ForeignKey, DateTime, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base, TimestampMixin
from src.models.category import CategoryType
from src.core.security import EncryptedString

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.family import FamilyGroup
    from src.models.category import Category
    from src.models.asset import AssetAccount
    from src.models.credit import CreditAccount


class TransactionSource(str, Enum):
    text = "text"
    voice = "voice"
    photo = "photo"
    manual = "manual"
    statement = "statement"


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_id_tx_date", "user_id", text("transaction_date DESC")),
        Index("ix_transactions_family_group_id_tx_date", "family_group_id", text("transaction_date DESC"), postgresql_where=text("family_group_id IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    family_group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("family_groups.id"), nullable=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    original_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    discount_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    type: Mapped[CategoryType] = mapped_column()
    asset_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("asset_accounts.id"), nullable=True)
    asset_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    exchange_rate: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    related_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    credit_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_accounts.id", ondelete="SET NULL"), nullable=True)
    item_name: Mapped[str | None] = mapped_column(EncryptedString(512), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[TransactionSource] = mapped_column(default=TransactionSource.manual)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="transactions")
    family_group: Mapped[Optional["FamilyGroup"]] = relationship("FamilyGroup", back_populates="transactions")
    category: Mapped["Category"] = relationship("Category", back_populates="transactions")
    asset_account: Mapped[Optional["AssetAccount"]] = relationship("AssetAccount", back_populates="transactions")
    related_transaction: Mapped[Optional["Transaction"]] = relationship("Transaction", remote_side="Transaction.id", foreign_keys=[related_transaction_id], post_update=True)
    credit_account: Mapped[Optional["CreditAccount"]] = relationship("CreditAccount", back_populates="transactions")

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category else None

    @property
    def asset_currency(self) -> str | None:
        return self.asset_account.currency if self.asset_account else None
