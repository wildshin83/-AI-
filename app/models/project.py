"""프로젝트 기본 정보와 진행 상태 모델."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ProjectStatus(StrEnum):
    QUOTATION = "견적"
    ORDERED = "수주"
    IN_PROGRESS = "진행"
    SETUP = "셋업"
    COMPLETED = "완료"


class Project(Base):
    """BOM, 견적, 도면, 경고가 연결되는 최상위 관리 단위."""

    __tablename__ = "projects"
    __table_args__ = (CheckConstraint("schedule_version > 0", name="ck_schedule_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_number: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    project_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    equipment_unit: Mapped[str] = mapped_column(String(160), nullable=False)
    manager_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ProjectStatus.QUOTATION.value,
        index=True,
    )
    target_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    incoming_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fob_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    schedule_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
