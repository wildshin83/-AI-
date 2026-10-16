"""Alembic 실행 시 앱의 데이터베이스 설정을 사용한다."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401
from app.config import paths
from app.db import Base, is_sqlite_database, migration_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", migration_database_url().replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB 연결 없이 SQL 마이그레이션을 생성한다."""

    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """현재 설정된 SQLite 또는 PostgreSQL DB에 마이그레이션을 적용한다."""

    paths.ensure_directories()
    engine_options = {
        "prefix": "sqlalchemy.",
        "poolclass": pool.NullPool,
    }
    if not is_sqlite_database():
        engine_options["connect_args"] = {"prepare_threshold": None}
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), **engine_options
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=is_sqlite_database(),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
