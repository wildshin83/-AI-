"""Excel 업로드 미리보기와 확정 흐름을 제공한다."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.excel_mapping import (
    MappingPreview,
    WorkbookKind,
    preview_mapping,
    validate_mapping,
)
from app.models.imports import MappingProfile, UploadBatch
from app.services.audit import record_audit


def create_preview_batch(
    session: Session,
    *,
    project_id: int,
    source_type: WorkbookKind,
    original_file_name: str,
    stored_path: Path,
) -> tuple[UploadBatch, MappingPreview]:
    """원본을 보관하고 자동 매핑 결과를 확정 전 미리보기로 만든다."""

    preview = preview_mapping(stored_path, source_type)
    profile = session.scalar(
        select(MappingProfile).where(MappingProfile.source_type == source_type.value)
    )
    if profile is not None:
        available_headers = set(preview.unmapped_headers) | set(preview.mapping.values())
        preferred_mapping = {
            field: header
            for field, header in profile.mapping.items()
            if header in available_headers
        }
        preview = MappingPreview(
            workbook_kind=preview.workbook_kind,
            sheet_name=preview.sheet_name,
            header_row=preview.header_row,
            mapping={**preview.mapping, **preferred_mapping},
            unmapped_headers=preview.unmapped_headers,
            issues=preview.issues,
        )
    batch = UploadBatch(
        project_id=project_id,
        source_type=source_type.value,
        status="preview",
        original_file_name=original_file_name,
        stored_path=str(stored_path),
        sheet_name=preview.sheet_name,
        header_row=preview.header_row,
        mapping=preview.mapping,
        issues=[issue.__dict__ for issue in preview.issues],
    )
    session.add(batch)
    session.flush()
    record_audit(
        session,
        action="upload.previewed",
        entity_type="upload_batch",
        entity_id=batch.id,
        details={"source_type": source_type.value, "project_id": project_id},
    )
    session.commit()
    session.refresh(batch)
    return batch, preview


def confirm_batch(
    session: Session,
    *,
    batch: UploadBatch,
    mapping: dict[str, str],
) -> list[str]:
    """사용자가 검토한 매핑을 확정하고 다음 업로드용 프로필로 저장한다."""

    workbook_kind = WorkbookKind(batch.source_type)
    issues = validate_mapping(mapping, workbook_kind)
    if issues:
        return [issue.message for issue in issues]

    batch.mapping = mapping
    batch.issues = []
    batch.status = "confirmed"
    batch.confirmed_at = datetime.now()
    profile = session.scalar(
        select(MappingProfile).where(MappingProfile.source_type == batch.source_type)
    )
    if profile is None:
        profile = MappingProfile(source_type=batch.source_type, mapping=mapping)
        session.add(profile)
    else:
        profile.mapping = mapping
    record_audit(
        session,
        action="upload.confirmed",
        entity_type="upload_batch",
        entity_id=batch.id,
        details={"source_type": batch.source_type, "project_id": batch.project_id},
    )
    session.commit()
    return []
