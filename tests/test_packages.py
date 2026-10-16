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


def test_schedule_dates_package_v2_roundtrip_and_legacy(account_db, tmp_path, monkeypatch):
    from datetime import date

    import pytest

    from app.models.project import Project
    from app.services.packages import export_project_package, import_project_package

    root = tmp_path / "package-files"
    local_paths = AppPaths(
        root=root,
        database=root / "data/db.sqlite3",
        files=root / "files",
        exports=root / "exports",
        backups=root / "backups",
        logs=root / "logs",
    )
    local_paths.ensure_directories()
    monkeypatch.setattr(packages, "paths", local_paths)
    project = Project(
        project_number="PACKAGE-1",
        project_name="Package",
        customer_name="Test",
        equipment_unit="Test",
        manager_name="Test",
        schedule_version=8,
        target_delivery_date=date(2026, 12, 1),
        incoming_date=date(2026, 11, 1),
        fob_date=date(2026, 11, 15),
    )
    account_db.add(project)
    account_db.commit()
    result = export_project_package(account_db, project=project, created_by="Test")
    path = Path(result.stored_path)
    with pytest.raises(ValueError, match="동일 프로젝트 번호"):
        import_project_package(account_db, package_path=path, imported_by="Test")
    for legacy in (False, True):
        manifest = read_package_manifest(path)
        manifest["project"]["number"] = f"PACKAGE-{'OLD' if legacy else 'NEW'}"
        if legacy:
            manifest["project"].pop("incoming_date", None)
            manifest["project"].pop("fob_date", None)
        new_path = tmp_path / f"{legacy}.zip"
        with ZipFile(new_path, "w") as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
        restored = import_project_package(account_db, package_path=new_path, imported_by="Test")
        assert restored.target_delivery_date == date(2026, 12, 1)
        assert restored.incoming_date == (None if legacy else date(2026, 11, 1))
        assert restored.fob_date == (None if legacy else date(2026, 11, 15))
        assert restored.schedule_version == 1


def test_backup_restore_preserves_current_state_as_a_separate_backup(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(packages, "is_sqlite_database", lambda: True)
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
