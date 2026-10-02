from enum import Enum
from typing import Optional

from sqlalchemy import Integer, String, BigInteger, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class CategoryType(str, Enum):
    income = "income"
    expense = "expense"


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(64))
    type: Mapped[CategoryType] = mapped_column()
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("user_id", "name", "type", name="uq_user_category_name_type"),
    )

    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="category")
    aliases: Mapped[list["UserItemAlias"]] = relationship("UserItemAlias", back_populates="category")
