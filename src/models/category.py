from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, BigInteger, Boolean, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.alias import UserItemAlias
    from src.models.transaction import Transaction


class CategoryType(str, Enum):
    income = "income"
    expense = "expense"
    transfer_out = "transfer_out"  # Перевод в депозит / покупка валюты
    transfer_in = "transfer_in"    # Вывод с депозита / продажа валюты


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(64))
    type: Mapped[CategoryType] = mapped_column()
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("user_id", "name", "type", name="uq_user_category_name_type"),
    )

    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="category")
    aliases: Mapped[list["UserItemAlias"]] = relationship("UserItemAlias", back_populates="category")
