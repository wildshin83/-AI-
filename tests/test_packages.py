import json
from pathlib import Path
from zipfile import ZipFile

from app.config import AppPaths
from app.storage import packages
from app.storage.packages import read_package_manifest


def test_package_manifest_can_be_read_without_overwriting(tmp_path: Path) -> None:
    package_path = tmp_path / "project.zip"
    with ZipFile(package_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"format_version": 1, "project": {}}))

    manifest = read_package_manifest(package_path)

    assert manifest["format_version"] == 1


def test_backup_restore_preserves_current_state_as_a_separate_backup(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "app-data"
    local_paths = AppPaths(
        root=root,
        database=root / "data" / "bom_service.sqlite3",
        files=root / "files",
        exports=root / "exports",
        backups=root / "backups",
        logs=root / "logs",
    )
    monkeypatch.setattr(packages, "paths", local_paths)
    local_paths.ensure_directories()
    local_paths.database.write_bytes(b"before")
    (local_paths.files / "drawing.txt").write_text("before", encoding="utf-8")
    backup = packages.create_local_backup()

    local_paths.database.write_bytes(b"after")
    (local_paths.files / "drawing.txt").write_text("after", encoding="utf-8")
    pre_restore_backup = packages.restore_local_backup(backup)

    assert local_paths.database.read_bytes() == b"before"
    assert (local_paths.files / "drawing.txt").read_text(encoding="utf-8") == "before"
    assert pre_restore_backup.is_file()


def test_backup_inspection_rejects_unsafe_archive_paths(tmp_path: Path) -> None:
    backup_path = tmp_path / "unsafe.zip"
    with ZipFile(backup_path, "w") as archive:
        archive.writestr("data/bom_service.sqlite3", "database")
        archive.writestr("../outside.txt", "unsafe")

    try:
        packages.inspect_local_backup(backup_path)
    except ValueError as error:
        assert "허용되지 않는 경로" in str(error)
    else:
        raise AssertionError("안전하지 않은 ZIP 경로를 거부해야 합니다.")
