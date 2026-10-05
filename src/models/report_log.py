from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.user import User


class ScheduledReportLog(Base, TimestampMixin):
    __tablename__ = "scheduled_report_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    report_type: Mapped[str] = mapped_column(String(16))  # "weekly", "monthly", "yearly"
    period_key: Mapped[str] = mapped_column(String(32))   # e.g. "2026-W40", "2026-10", "2026"
    status: Mapped[str] = mapped_column(String(16))       # "sent", "blocked", "failed"
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", backref="scheduled_reports")

    __table_args__ = (
        UniqueConstraint("user_id", "report_type", "period_key", name="uq_user_report_period"),
    )
