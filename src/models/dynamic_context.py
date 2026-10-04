from __future__ import annotations

import uuid
from sqlalchemy import BigInteger, String, Integer, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base, TimestampMixin


class DynamicFewShot(Base, TimestampMixin):
    """Dynamic few-shot learning catalog for LLM prompts without code hardcoding."""
    __tablename__ = "dynamic_few_shots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    domain_tag: Mapped[str] = mapped_column(String(64), index=True)
    raw_query: Mapped[str] = mapped_column(String(512), nullable=False)
    expected_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserClassificationFeedback(Base, TimestampMixin):
    """Runtime feedback log from Telegram button flips for active learning."""
    __tablename__ = "user_classification_feedback"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False)
    original_text: Mapped[str | None] = mapped_column(Text)
    original_type: Mapped[str] = mapped_column(String(32), nullable=False)
    corrected_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corrected_category_id: Mapped[int] = mapped_column(Integer, nullable=False)
