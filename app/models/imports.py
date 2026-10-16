"""Excel 원본, 매핑 미리보기, 확정 매핑 규칙을 저장하는 모델."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UploadBatch(Base):
    """원본 Excel과 사용자 확정 전/후 매핑을 보존한다."""

    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="preview", index=True)
    original_file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    header_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mapping: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class MappingProfile(Base):
    """파일 유형별로 사용자가 확정한 마지막 열 매핑 규칙."""

    __tablename__ = "mapping_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    mapping: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
