"""ERP 원본 이력과 사용자가 확정한 BOM 매칭 모델."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ERPTransaction(Base):
    """ERP Excel의 한 행을 보존한 이력 레코드.

    ``erp_updated_at``은 현재 제공 양식의 '최종수정일'이며 거래일로 해석하지 않는다.
    """

    __tablename__ = "erp_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    upload_batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id"), nullable=False, index=True
    )
    part_number: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    normalized_part_number: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    part_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    material: Mapped[str | None] = mapped_column(String(200), nullable=True)
    specification: Mapped[str | None] = mapped_column(String(300), nullable=True)
    normalized_specification: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    maker: Mapped[str | None] = mapped_column(String(160), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    item_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    ordered_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    received_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    delivered_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    required_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    planned_delivery_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    revised_delivery_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    erp_updated_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, index=True)
    purchase_order_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    eco_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    erp_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )


class ErpMatch(Base):
    """BOM 품목과 ERP 이력의 후보 검토·확정 이력."""

    __tablename__ = "erp_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bom_item_id: Mapped[int] = mapped_column(ForeignKey("bom_items.id"), nullable=False, index=True)
    erp_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("erp_transactions.id"), nullable=False, index=True
    )
    match_method: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="candidate", index=True)
    review_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    review_evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    confirmation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )
