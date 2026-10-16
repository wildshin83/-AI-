"""로컬 앱 기반 기능의 최소 회귀 테스트."""

from fastapi.testclient import TestClient

from app.config import AppPaths
from app.main import app


def test_health_check_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "bom-management-service",
    }


def test_configured_paths_create_required_directories(tmp_path) -> None:
    root = tmp_path / "bom-data"
    paths = AppPaths(
        root=root,
        database=root / "data" / "bom_service.sqlite3",
        files=root / "files",
        exports=root / "exports",
        backups=root / "backups",
        logs=root / "logs",
    )

    paths.ensure_directories()

    assert paths.database.parent.is_dir()
    assert paths.files.is_dir()
    assert paths.exports.is_dir()
    assert paths.backups.is_dir()
    assert paths.logs.is_dir()
