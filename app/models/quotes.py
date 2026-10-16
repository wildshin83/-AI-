"""내부 검토와 고객 판매 견적을 분리한 견적 차수 스냅샷 모델."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class QuoteVersion(Base):
    """한 프로젝트의 작성 중 또는 제출 완료 고객 견적 차수."""

    __tablename__ = "quote_versions"
    __table_args__ = (UniqueConstraint("project_id", "version_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    bom_revision_id: Mapped[int] = mapped_column(ForeignKey("bom_revisions.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    submission_date: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    submission_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class QuoteItem(Base):
    """견적 차수 생성 시점의 BOM·판매단가 스냅샷."""

    __tablename__ = "quote_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_version_id: Mapped[int] = mapped_column(
        ForeignKey("quote_versions.id"), nullable=False, index=True
    )
    bom_item_id: Mapped[int | None] = mapped_column(ForeignKey("bom_items.id"), nullable=True)
    drawing_number: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    item_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    item_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    material: Mapped[str | None] = mapped_column(String(200), nullable=True)
    treatment: Mapped[str | None] = mapped_column(String(200), nullable=True)
    specification: Mapped[str | None] = mapped_column(String(300), nullable=True)
    maker: Mapped[str | None] = mapped_column(String(160), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    material_cost: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0")
    )
    machining_cost: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0")
    )
    treatment_cost: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0")
    )
    purchased_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0")
    )
    memo: Mapped[str | None] = mapped_column(Text(), nullable=True)


class QuoteAdjustment(Base):
    """이윤·일반관리비 등 품목 외 고객 견적 부대 항목."""

    __tablename__ = "quote_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_version_id: Mapped[int] = mapped_column(
        ForeignKey("quote_versions.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    memo: Mapped[str | None] = mapped_column(Text(), nullable=True)
