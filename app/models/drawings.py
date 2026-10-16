"""도면·모델·캡처 원본과 BOM Rev 연결 모델."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DrawingFile(Base):
    """삭제 대신 보존하는 설계 근거 파일 메타데이터."""

    __tablename__ = "drawing_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    bom_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("bom_items.id"), nullable=True, index=True
    )
    bom_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("bom_revisions.id"), nullable=True, index=True
    )
    drawing_number: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    drawing_revision: Mapped[str | None] = mapped_column(String(80), nullable=True)
    file_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    original_file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    stored_path: Mapped[str] = mapped_column(Text(), nullable=False)
    file_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(100), nullable=False)
    memo: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )
