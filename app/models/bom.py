"""BOM Rev와 품목 스냅샷 모델."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BomRevision(Base):
    """Inventor BOM Excel을 기준으로 고정하는 한 시점의 BOM."""

    __tablename__ = "bom_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    upload_batch_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id"), nullable=False, unique=True
    )
    revision_name: Mapped[str] = mapped_column(String(80), nullable=False)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )


class BomItem(Base):
    """BOM Rev에 속하는 품목 스냅샷. 품목 구분은 사용자가 다음 단계에서 확정한다."""

    __tablename__ = "bom_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bom_revision_id: Mapped[int] = mapped_column(
        ForeignKey("bom_revisions.id"), nullable=False, index=True
    )
    source_item_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    drawing_number: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    normalized_drawing_number: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    component: Mapped[str | None] = mapped_column(String(300), nullable=True)
    material: Mapped[str | None] = mapped_column(String(200), nullable=True)
    treatment: Mapped[str | None] = mapped_column(String(200), nullable=True)
    specification: Mapped[str | None] = mapped_column(String(300), nullable=True)
    maker: Mapped[str | None] = mapped_column(String(160), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    item_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
