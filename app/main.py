"""로컬 BOM 관리 서비스의 HTTP 진입점."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import paths
from app.routes.alerts import router as alerts_router
from app.routes.bom import router as bom_router
from app.routes.drawings import router as drawings_router
from app.routes.erp import router as erp_router
from app.routes.operations import router as operations_router
from app.routes.projects import router as projects_router
from app.routes.quotes import router as quotes_router
from app.routes.uploads import router as uploads_router


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
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(projects_router)
app.include_router(operations_router)
app.include_router(uploads_router)
app.include_router(bom_router)
app.include_router(drawings_router)
app.include_router(erp_router)
app.include_router(alerts_router)
app.include_router(quotes_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """설치 및 로컬 실행 상태를 확인한다."""

    return {"status": "ok", "service": "bom-management-service"}
