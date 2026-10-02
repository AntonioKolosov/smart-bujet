import uuid
from typing import Optional

from sqlalchemy import String, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from src.models.base import Base, TimestampMixin


class FamilyGroup(Base, TimestampMixin):
    __tablename__ = "family_groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64))
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    invite_code: Mapped[str] = mapped_column(String(32), unique=True)

    owner: Mapped["User"] = relationship("User", back_populates="owned_families", foreign_keys=[owner_id])
    members: Mapped[list["User"]] = relationship("User", back_populates="family_group", foreign_keys="[User.family_group_id]")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="family_group")
