from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, String, Boolean, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.alias import UserItemAlias
    from src.models.family import FamilyGroup
    from src.models.transaction import Transaction


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(String(3), default="KZT")
    initial_balance: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, default=None)
    family_group_id: Mapped[UUID | None] = mapped_column(ForeignKey("family_groups.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
    aliases: Mapped[list["UserItemAlias"]] = relationship("UserItemAlias", back_populates="user")
    family_group: Mapped["FamilyGroup" | None] = relationship("FamilyGroup", back_populates="members", foreign_keys=[family_group_id])
    owned_families: Mapped[list["FamilyGroup"]] = relationship("FamilyGroup", back_populates="owner", foreign_keys="[FamilyGroup.owner_id]")
