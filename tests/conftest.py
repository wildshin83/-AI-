"""실제 업무 DB를 사용하지 않는 계정·일정 테스트 환경."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base, get_session
from app.main import app
from app.models.auth import AuthUser
from app.security import COOKIE_NAME, create_session_token
from app.services.auth import hash_password

TEST_PASSWORD = "Example-test-password-123"


@pytest.fixture(autouse=True)
def isolated_app_paths(tmp_path, monkeypatch):
    import app.config as config
    import app.main as main

    root = tmp_path / "app"
    paths = config.AppPaths(
        root=root,
        database=root / "data/app.sqlite3",
        files=root / "files",
        exports=root / "exports",
        backups=root / "backups",
        logs=root / "logs",
    )
    monkeypatch.setattr(config, "paths", paths)
    monkeypatch.setattr(main, "paths", paths)
    local_engine = create_engine(f"sqlite:///{(tmp_path / 'health.sqlite3').as_posix()}")
    monkeypatch.setattr(main, "engine", local_engine)
    monkeypatch.delenv("BOM_SMTP_HOST", raising=False)
    monkeypatch.delenv("BOM_SMTP_USERNAME", raising=False)
    monkeypatch.delenv("BOM_SMTP_PORT", raising=False)
    monkeypatch.delenv("BOM_SMTP_STARTTLS", raising=False)
    yield
    local_engine.dispose()


@pytest.fixture
def account_db(monkeypatch):
    import app.security as security

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(security, "SessionLocal", factory)
    monkeypatch.setenv("BOM_SESSION_SECRET", "test-only-session-secret-1234567890")
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture
def accounts(account_db):
    hashed = hash_password(TEST_PASSWORD)
    users = []
    for index, name in enumerate(("member", "reviewer", "admin")):
        user = AuthUser(
            email=f"{name}@example.test",
            display_name=name,
            password_hash=hashed,
            is_admin=index == 2,
            must_change_password=False,
        )
        if hasattr(AuthUser, "permission_level"):
            user.permission_level = 1 if index == 0 else 2
        account_db.add(user)
        users.append(user)
    account_db.commit()
    return users


@pytest.fixture
def web_client(account_db):
    def session_override():
        yield account_db

    app.dependency_overrides[get_session] = session_override
    with TestClient(app, headers={"origin": "http://testserver"}) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sign_in(web_client):
    def login(user):
        web_client.cookies.set(COOKIE_NAME, create_session_token(user))
        return web_client

    return login
