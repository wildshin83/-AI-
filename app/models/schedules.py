"""프로젝트 일정 변경 승인 기록."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ScheduleChangeRequest(Base):
    __tablename__ = "schedule_change_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','conflicted')",
            name="ck_schedule_request_status",
        ),
        CheckConstraint("base_version > 0", name="ck_request_base_version"),
        Index("ix_schedule_request_project_status", "project_id", "status"),
        Index("ix_schedule_request_requester", "requested_by_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("auth_users.id"), nullable=False)
    requested_by_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    old_target_delivery_date: Mapped[date | None] = mapped_column(Date)
    old_incoming_date: Mapped[date | None] = mapped_column(Date)
    old_fob_date: Mapped[date | None] = mapped_column(Date)
    proposed_target_delivery_date: Mapped[date | None] = mapped_column(Date)
    proposed_incoming_date: Mapped[date | None] = mapped_column(Date)
    proposed_fob_date: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("auth_users.id"))
    reviewed_by_name: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_comment: Mapped[str | None] = mapped_column(Text)
