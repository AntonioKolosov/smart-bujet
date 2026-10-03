import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Numeric, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.transaction import Transaction


class AssetType(str, Enum):
    deposit = "deposit"            # Банковский вклад / депозит
    currency = "currency"          # Наличная/безналичная валюта (USD, EUR и т.д.)
    savings = "savings"            # Копилка / сейф
    investment = "investment"      # Инвестиции / акции


class AssetAccount(Base, TimestampMixin):
    __tablename__ = "asset_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    type: Mapped[AssetType] = mapped_column(String(32), default=AssetType.deposit)
    currency: Mapped[str] = mapped_column(String(3), default="KZT")
    balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0)
    interest_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship("User", backref="asset_accounts")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="asset_account")
