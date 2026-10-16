"""로컬 BOM 관리 서비스의 HTTP 진입점."""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import paths
from app.db import engine, is_sqlite_database
from app.routes.admin import router as admin_router
from app.routes.alerts import router as alerts_router
from app.routes.auth import router as auth_router
from app.routes.bom import router as bom_router
from app.routes.drawings import router as drawings_router
from app.routes.erp import router as erp_router
from app.routes.operations import router as operations_router
from app.routes.projects import router as projects_router
from app.routes.quotes import router as quotes_router
from app.routes.schedules import router as schedules_router
from app.routes.uploads import router as uploads_router
from app.security import AuthenticationMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    """앱 시작 전에 로컬 데이터 디렉터리를 준비한다."""

    paths.ensure_directories()
    yield


app = FastAPI(
    title="BOM 관리 서비스",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)
css_path = Path(__file__).resolve().parent / "static" / "app.css"
app.state.static_version = hashlib.sha256(css_path.read_bytes()).hexdigest()[:12]
app.add_middleware(AuthenticationMiddleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(projects_router)
app.include_router(operations_router)
app.include_router(uploads_router)
app.include_router(bom_router)
app.include_router(drawings_router)
app.include_router(erp_router)
app.include_router(alerts_router)
app.include_router(quotes_router)
app.include_router(schedules_router)


@app.get("/health", tags=["system"])
def health_check(details: bool = False) -> JSONResponse:
    """DB 연결을 확인하고 민감정보 없이 현재 DB 종류만 반환한다."""

    database = "sqlite" if is_sqlite_database() else "postgresql"
    content = {"status": "ok", "service": "bom-management-service"}
    if details:
        content["database"] = database
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        content["status"] = "unavailable"
        return JSONResponse(status_code=503, content=content)
    return JSONResponse(content=content)
