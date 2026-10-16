"""도면·첨부 원본의 안전한 로컬 저장 공통 기능."""

from pathlib import Path
from uuid import uuid4

from app.config import paths

ALLOWED_SUFFIXES = {".ipt", ".iam", ".idw", ".dwg", ".pdf", ".png", ".jpg", ".jpeg"}


def store_drawing_upload(*, project_id: int, original_file_name: str, content: bytes) -> Path:
    suffix = Path(original_file_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("모델·도면·PDF·이미지 파일만 업로드할 수 있습니다.")
    destination_directory = paths.files / "drawings" / f"project-{project_id}"
    destination_directory.mkdir(parents=True, exist_ok=True)
    destination = destination_directory / f"{uuid4().hex}{suffix}"
    destination.write_bytes(content)
    return destination
