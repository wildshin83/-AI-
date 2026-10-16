"""SQLAlchemy 엔진과 세션 생성을 제공한다.

도메인 모델은 이후 단계에서 `app.models`에 추가한다. 이 모듈은 UI나
업무 규칙에 의존하지 않아 SQLite에서 중앙 DB로의 이전을 지원한다.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import paths


class Base(DeclarativeBase):
    """모든 ORM 모델의 공통 베이스."""


def database_url() -> str:
    """운영체제 경로를 SQLite URL로 변환한다."""

    return f"sqlite:///{paths.database.as_posix()}"


def create_local_engine():
    """로컬 SQLite 엔진을 생성한다.

    `check_same_thread=False`는 로컬 웹 서버의 요청 처리 스레드에서 같은
    데이터베이스 연결 설정을 사용할 수 있게 한다. 세션은 요청 단위로 생성한다.
    """

    return create_engine(
        database_url(),
        connect_args={"check_same_thread": False},
        future=True,
    )


engine = create_local_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    """FastAPI 의존성으로 사용할 요청 단위 DB 세션."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
