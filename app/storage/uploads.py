"""사용자가 올린 Excel 원본 파일을 안전하게 로컬 저장소에 보관한다."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.config import paths


def store_excel_upload(*, project_id: int, original_file_name: str, content: bytes) -> Path:
    """원본 이름을 경로에 사용하지 않고 UUID 파일명으로 보관한다."""

    suffix = Path(original_file_name).suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        raise ValueError("Excel 파일(.xlsx 또는 .xlsm)만 업로드할 수 있습니다.")
    destination_directory = paths.files / "uploads" / f"project-{project_id}"
    destination_directory.mkdir(parents=True, exist_ok=True)
    destination = destination_directory / f"{uuid4().hex}{suffix}"
    destination.write_bytes(content)
    return destination
