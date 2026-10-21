from __future__ import annotations

import uuid
from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.user import User


class FactCategory(str, Enum):
    goal = "goal"
    habit = "habit"
    schedule = "schedule"
    constraint = "constraint"
    other = "other"


class UserAgentMemory(Base, TimestampMixin):
    """
    Long-term agent memory storing user facts, habits, goals, schedules, and constraints.
    Injected into AI advice prompts to personalize financial recommendations.
    """
    __tablename__ = "user_agent_memories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(32), default=FactCategory.other.value, index=True, nullable=False)
    fact_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="agent_memories")
