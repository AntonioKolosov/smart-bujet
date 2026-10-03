from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.category import Category


class UserItemAlias(Base, TimestampMixin):
    __tablename__ = "user_item_aliases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    item_name_normalized: Mapped[str] = mapped_column(String(128), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    usage_count: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint("user_id", "item_name_normalized", name="uq_user_item_alias"),
    )

    user: Mapped["User"] = relationship("User", back_populates="aliases")
    category: Mapped["Category"] = relationship("Category", back_populates="aliases")
