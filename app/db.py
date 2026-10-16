"""SQLAlchemy 엔진과 세션 생성, SQLite/Supabase PostgreSQL 선택을 제공한다."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import paths

load_dotenv()


class Base(DeclarativeBase):
    """모든 ORM 모델의 공통 베이스."""


def _normalize_database_url(configured_url: str) -> str:
    url = make_url(configured_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername != "postgresql+psycopg":
        raise ValueError(
            "BOM_DATABASE_URL은 Supabase PostgreSQL 연결 URL이어야 합니다 "
            "(postgresql:// 또는 postgresql+psycopg://)."
        )

    query = dict(url.query)
    query.setdefault("sslmode", "require")
    if query["sslmode"] not in {"require", "verify-ca", "verify-full"}:
        raise ValueError(
            "Supabase PostgreSQL 연결에는 SSL이 필요합니다. sslmode=require 이상을 지정하세요."
        )
    return url.set(query=query).render_as_string(hide_password=False)


def database_url() -> str:
    """앱 런타임용 URL을 반환하며, 미설정 개발 환경은 로컬 SQLite를 사용한다."""

    configured_url = os.getenv("BOM_DATABASE_URL", "").strip()
    if not configured_url:
        return f"sqlite:///{paths.database.as_posix()}"
    return _normalize_database_url(configured_url)


def migration_database_url() -> str:
    """DDL 권한이 분리된 마이그레이션 URL을 반환한다."""

    runtime_configured = os.getenv("BOM_DATABASE_URL", "").strip()
    configured_url = os.getenv("BOM_MIGRATION_DATABASE_URL", "").strip()
    if not runtime_configured:
        if configured_url:
            raise RuntimeError(
                "원격 DB 마이그레이션 전에 런타임 BOM_DATABASE_URL도 설정해야 합니다."
            )
        return database_url()
    runtime_url = _normalize_database_url(runtime_configured)
    if make_url(runtime_url).get_backend_name() == "sqlite":
        if configured_url:
            raise RuntimeError("SQLite 설정과 Supabase 마이그레이션 URL을 함께 사용할 수 없습니다.")
        return runtime_url
    if not configured_url:
        raise RuntimeError(
            "Supabase 스키마 변경에는 일시적인 BOM_MIGRATION_DATABASE_URL이 필요합니다."
        )
    return _normalize_database_url(configured_url)


def is_sqlite_database() -> bool:
    """현재 설정이 로컬 SQLite를 가리키는지 반환한다."""

    return make_url(database_url()).get_backend_name() == "sqlite"


def create_database_engine():
    """설정된 DB 엔진을 생성한다. Supabase 연결은 TLS와 연결 사전 점검을 사용한다."""

    url = database_url()
    if make_url(url).get_backend_name() == "sqlite":
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            future=True,
        )
    return create_engine(
        url,
        connect_args={"prepare_threshold": None},
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=1,
        pool_recycle=1800,
        future=True,
    )


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    """FastAPI 의존성으로 사용할 요청 단위 DB 세션."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
