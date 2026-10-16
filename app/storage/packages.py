"""로컬 프로젝트 패키지·백업 파일 생성 공통 기능."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from app.config import paths
from app.db import is_sqlite_database


def create_json_package(
    *, file_stem: str, payload: dict[str, object], backup: bool = False
) -> Path:
    directory = paths.backups if backup else paths.exports
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination = directory / f"{file_stem}_{stamp}.zip"
    with ZipFile(destination, "x", ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json", json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        )
    return destination


def read_package_manifest(path: Path) -> dict[str, object]:
    with ZipFile(path) as archive:
        return json.loads(archive.read("manifest.json").decode("utf-8"))


def create_local_backup() -> Path:
    """SQLite DB와 관리 파일을 한 ZIP에 복사하며 기존 백업은 보존한다."""

    if not is_sqlite_database():
        raise RuntimeError(
            "이 기능은 로컬 SQLite 백업 전용입니다. Supabase PostgreSQL은 별도 백업 절차를 사용하세요."
        )
    paths.ensure_directories()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination = paths.backups / f"local_backup_{stamp}.zip"
    with ZipFile(destination, "x", ZIP_DEFLATED) as archive:
        if paths.database.is_file():
            archive.write(paths.database, "data/bom_service.sqlite3")
        for file_path in paths.files.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(paths.root).as_posix())
    return destination


def inspect_local_backup(path: Path) -> dict[str, object]:
    """복원 전 ZIP 구성과 필수 DB 포함 여부만 안전하게 검사한다."""

    with ZipFile(path) as archive:
        member_names = [entry.filename for entry in archive.infolist() if not entry.is_dir()]
    invalid_names = [name for name in member_names if _unsafe_archive_member(name)]
    if invalid_names:
        raise ValueError("백업 파일에 허용되지 않는 경로가 포함되어 있습니다.")
    if "data/bom_service.sqlite3" not in member_names:
        raise ValueError("백업 파일에 SQLite 데이터베이스가 없습니다.")
    return {
        "database_included": True,
        "file_count": len([name for name in member_names if name.startswith("files/")]),
        "member_count": len(member_names),
    }


def _unsafe_archive_member(member_name: str) -> bool:
    member_path = Path(member_name)
    return (
        member_name.startswith(("/", "\\"))
        or ".." in member_path.parts
        or not (
            member_name == "data/bom_service.sqlite3" or member_name.startswith("files/")
        )
    )


def restore_local_backup(path: Path) -> Path:
    """검증된 백업으로 DB·첨부 파일을 복원하고, 기존 상태는 자동 백업한다."""

    if not is_sqlite_database():
        raise RuntimeError(
            "SQLite 백업을 Supabase PostgreSQL에 복원할 수 없습니다. Supabase 복구 절차를 사용하세요."
        )
    inspect_local_backup(path)
    paths.ensure_directories()
    pre_restore_backup = create_local_backup()
    with TemporaryDirectory(prefix="bom-restore-") as temporary_directory:
        staging_root = Path(temporary_directory)
        staged_database = staging_root / "data" / "bom_service.sqlite3"
        staged_files = staging_root / "files"
        with ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir() or _unsafe_archive_member(member.filename):
                    continue
                target = staging_root / member.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
        if not staged_database.is_file():
            raise ValueError("복원용 SQLite 데이터베이스를 추출하지 못했습니다.")

        old_database = staging_root / "previous.sqlite3"
        if paths.database.is_file():
            shutil.copy2(paths.database, old_database)
        rollback_files = paths.root / f"restore_rollback_{datetime.now():%Y%m%d_%H%M%S_%f}"
        moved_files = False
        try:
            if paths.files.exists():
                shutil.move(str(paths.files), str(rollback_files))
                moved_files = True
            if staged_files.exists():
                shutil.move(str(staged_files), str(paths.files))
            else:
                paths.files.mkdir()
            shutil.copy2(staged_database, paths.database)
        except OSError:
            if paths.files.exists():
                shutil.rmtree(paths.files)
            if moved_files and rollback_files.exists():
                shutil.move(str(rollback_files), str(paths.files))
            if old_database.is_file():
                shutil.copy2(old_database, paths.database)
            raise
    return pre_restore_backup
