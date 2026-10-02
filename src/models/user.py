from typing import Optional
from uuid import UUID

from sqlalchemy import BigInteger, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(String(3), default="KZT")
    family_group_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("family_groups.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
    aliases: Mapped[list["UserItemAlias"]] = relationship("UserItemAlias", back_populates="user")
    family_group: Mapped[Optional["FamilyGroup"]] = relationship("FamilyGroup", back_populates="members", foreign_keys=[family_group_id])
    owned_families: Mapped[list["FamilyGroup"]] = relationship("FamilyGroup", back_populates="owner", foreign_keys="[FamilyGroup.owner_id]")
