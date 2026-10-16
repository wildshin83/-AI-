"""기존 계정·납기 데이터를 보존하는 스키마 갱신 검증."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def test_schedule_migration_preserves_existing_values(tmp_path, monkeypatch):
    import app.db as db

    url = f"sqlite:///{(tmp_path / 'migration.sqlite3').as_posix()}"
    monkeypatch.setattr(db, "migration_database_url", lambda: url)
    monkeypatch.setattr(db, "is_sqlite_database", lambda: True)
    config = Config("alembic.ini")
    command.upgrade(config, "20261016_0011")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO auth_users (email, display_name, password_hash, is_admin) "
                "VALUES ('user@example.test', 'User', 'unused', 0), "
                "('admin@example.test', 'Admin', 'unused', 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO projects (project_number, project_name, customer_name, "
                "equipment_unit, "
                "manager_name, status, is_archived, target_delivery_date) "
                "VALUES ('T-1', 'Test', 'Test', 'Test', 'Test', '견적', 0, '2026-11-15')"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT permission_level FROM auth_users ORDER BY id")
        ).scalars().all() == [1, 2]
        assert connection.execute(
            text(
                "SELECT target_delivery_date, incoming_date, fob_date, "
                "schedule_version FROM projects"
            )
        ).one() == ("2026-11-15", None, None, 1)
    engine.dispose()
