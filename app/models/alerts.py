"""가격 기준과 납기 위험 경고·조치 이력 모델."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PriceRecord(Base):
    """ERP 참고단가와 사용자가 확정한 내부/판매 단가를 분리 보관한다."""

    __tablename__ = "price_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bom_item_id: Mapped[int] = mapped_column(ForeignKey("bom_items.id"), nullable=False, index=True)
    erp_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("erp_transactions.id"), nullable=True, index=True
    )
    price_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    basis_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    memo: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )


class ItemAlertRule(Base):
    """중요 품목에 적용하는 기본값보다 우선하는 경고 임계값."""

    __tablename__ = "item_alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bom_item_id: Mapped[int] = mapped_column(
        ForeignKey("bom_items.id"), nullable=False, unique=True, index=True
    )
    is_critical: Mapped[bool] = mapped_column(default=True, nullable=False)
    price_increase_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    long_lead_days: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    overdue_days: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )


class Alert(Base):
    """계산으로 생성된 위험과 담당자 조치 상태."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    bom_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("bom_items.id"), nullable=True, index=True
    )
    alert_code: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="unread", index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_fingerprint: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    due_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AlertAction(Base):
    """경고 확인·조치·해결·예외 승인에 대한 추적 가능한 이력."""

    __tablename__ = "alert_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), nullable=False, index=True)
    action_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action_note: Mapped[str] = mapped_column(Text(), nullable=False)
    alternative_reviewed: Mapped[bool | None] = mapped_column(nullable=True)
    expected_resolution_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )
