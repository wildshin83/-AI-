"""도면 원본 등록과 품목/Rev 연결 유스케이스."""

from pathlib import Path

from sqlalchemy.orm import Session

from app.models.bom import BomItem, BomRevision
from app.models.drawings import DrawingFile
from app.services.audit import record_audit


def register_drawing_file(
    session: Session,
    *,
    project_id: int,
    bom_item: BomItem | None,
    bom_revision: BomRevision | None,
    drawing_number: str,
    drawing_revision: str | None,
    file_type: str,
    original_file_name: str,
    stored_path: Path,
    file_content: bytes | None = None,
    mime_type: str | None,
    uploaded_by: str,
    memo: str | None,
) -> DrawingFile:
    if not drawing_number.strip() or not uploaded_by.strip():
        raise ValueError("도면번호와 등록자는 필수입니다.")
    if bom_item and bom_revision and bom_item.bom_revision_id != bom_revision.id:
        raise ValueError("품목과 BOM Rev의 연결이 일치하지 않습니다.")
    drawing = DrawingFile(
        project_id=project_id,
        bom_item_id=bom_item.id if bom_item else None,
        bom_revision_id=bom_revision.id if bom_revision else None,
        drawing_number=drawing_number.strip(),
        drawing_revision=drawing_revision.strip() if drawing_revision else None,
        file_type=file_type,
        original_file_name=original_file_name,
        stored_path=str(stored_path),
        file_content=file_content,
        mime_type=mime_type,
        uploaded_by=uploaded_by.strip(),
        memo=memo.strip() if memo else None,
    )
    session.add(drawing)
    session.flush()
    record_audit(
        session,
        action="drawing_file.registered",
        entity_type="drawing_file",
        entity_id=drawing.id,
        actor_name=uploaded_by.strip(),
        details={"project_id": project_id, "file_type": file_type},
    )
    session.commit()
    return drawing
