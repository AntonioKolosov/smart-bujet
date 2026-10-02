import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Numeric, String, Text, BigInteger, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.models.base import Base, TimestampMixin
from src.models.category import CategoryType


class TransactionSource(str, Enum):
    text = "text"
    voice = "voice"
    photo = "photo"
    manual = "manual"


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    family_group_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("family_groups.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    original_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    discount_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    type: Mapped[CategoryType] = mapped_column()
    asset_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("asset_accounts.id"), nullable=True)
    asset_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    exchange_rate: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    item_name: Mapped[Optional[str]] = mapped_column(String(255))
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[TransactionSource] = mapped_column()
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="transactions")
    family_group: Mapped[Optional["FamilyGroup"]] = relationship("FamilyGroup", back_populates="transactions")
    category: Mapped["Category"] = relationship("Category", back_populates="transactions")
    asset_account: Mapped[Optional["AssetAccount"]] = relationship("AssetAccount", back_populates="transactions")

    @property
    def category_name(self) -> Optional[str]:
        return self.category.name if self.category else None
