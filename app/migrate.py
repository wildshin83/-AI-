"""설정된 SQLite 또는 Supabase PostgreSQL에 Alembic 마이그레이션을 적용한다."""

from __future__ import annotations

import os

from alembic import command
from alembic.config import Config

from app.db import is_sqlite_database


def main() -> None:
    """SQLite 개발 DB는 갱신하고, Supabase는 별도 마이그레이션 URL이 있을 때만 갱신한다."""

    if not is_sqlite_database():
        if not os.getenv("BOM_MIGRATION_DATABASE_URL", "").strip():
            print("Supabase 자동 마이그레이션을 건너뜁니다. 앱 런타임은 기존 스키마를 사용합니다.")
            return

    command.upgrade(Config("alembic.ini"), "head")


if __name__ == "__main__":
    main()
