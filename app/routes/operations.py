"""프로젝트 출력·패키지·백업 실행 화면."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import paths, reference_material_path
from app.db import get_session, is_sqlite_database
from app.models.alerts import Alert
from app.models.bom import BomItem, BomRevision
from app.models.project import Project
from app.models.quotes import QuoteItem, QuoteVersion
from app.services.bom import revision_changes
from app.services.packages import (
    compare_project_package,
    export_project_package,
    import_project_package,
)
from app.storage.packages import create_local_backup, restore_local_backup

router = APIRouter(tags=["operations"])
templates = Jinja2Templates(directory="app/templates")


def _project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    return project


@router.get("/projects/{project_id}/operations")
def operations_page(request: Request, project_id: int, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request,
        "operations/index.html",
        {
            "project": _project_or_404(session, project_id),
            "sqlite_database": is_sqlite_database(),
        },
    )


@router.post("/projects/{project_id}/exports/bom")
def bom_export(project_id: int, session: Session = Depends(get_session)):
    from app.exporters.excel import export_bom

    project = _project_or_404(session, project_id)
    revision = session.scalar(
        select(BomRevision)
        .where(BomRevision.project_id == project.id)
        .order_by(BomRevision.id.desc())
    )
    if revision is None:
        raise HTTPException(status_code=422, detail="출력할 BOM Rev가 없습니다.")
    output = paths.exports / f"{project.project_number}_BOM_{revision.revision_name}.xlsx"
    export_bom(
        output,
        items=list(session.scalars(select(BomItem).where(BomItem.bom_revision_id == revision.id))),
        alerts=list(session.scalars(select(Alert).where(Alert.project_id == project.id))),
    )
    return FileResponse(output, filename=output.name)


@router.post("/projects/{project_id}/exports/purchase-coordination")
def purchase_coordination_export(project_id: int, session: Session = Depends(get_session)):
    from app.exporters.excel import export_purchase_coordination

    project = _project_or_404(session, project_id)
    revision = session.scalar(
        select(BomRevision)
        .where(BomRevision.project_id == project.id)
        .order_by(BomRevision.id.desc())
    )
    if revision is None:
        raise HTTPException(status_code=422, detail="출력할 BOM Rev가 없습니다.")
    output = paths.exports / f"{project.project_number}_구매협의.xlsx"
    export_purchase_coordination(
        output,
        items=list(session.scalars(select(BomItem).where(BomItem.bom_revision_id == revision.id))),
        alerts=list(session.scalars(select(Alert).where(Alert.project_id == project.id))),
    )
    return FileResponse(output, filename=output.name)


@router.post("/projects/{project_id}/exports/bom-comparison")
def bom_comparison_export(project_id: int, session: Session = Depends(get_session)):
    from app.exporters.excel import export_bom_revision_comparison

    project = _project_or_404(session, project_id)
    revision = session.scalar(
        select(BomRevision)
        .where(BomRevision.project_id == project.id)
        .order_by(BomRevision.id.desc())
    )
    if revision is None:
        raise HTTPException(status_code=422, detail="비교할 BOM Rev가 없습니다.")
    output = paths.exports / f"{project.project_number}_BOM_Rev비교.xlsx"
    export_bom_revision_comparison(output, changes=revision_changes(session, revision))
    return FileResponse(output, filename=output.name)


@router.post("/projects/{project_id}/exports/cost-summary")
def cost_summary_export(project_id: int, session: Session = Depends(get_session)):
    from app.exporters.excel import export_cost_summary

    project = _project_or_404(session, project_id)
    quote = session.scalar(
        select(QuoteVersion)
        .where(QuoteVersion.project_id == project.id)
        .order_by(QuoteVersion.version_number.desc())
    )
    if quote is None:
        raise HTTPException(status_code=422, detail="출력할 견적 차수가 없습니다.")
    output = paths.exports / f"{project.project_number}_원가집계.xlsx"
    export_cost_summary(
        output,
        items=list(
            session.scalars(select(QuoteItem).where(QuoteItem.quote_version_id == quote.id))
        ),
    )
    return FileResponse(output, filename=output.name)


@router.post("/projects/{project_id}/exports/customer-quote")
def customer_quote_export(project_id: int, session: Session = Depends(get_session)):
    from app.exporters.excel import export_customer_quote
    from app.services.spreadsheet_calculation import (
        SpreadsheetCalculationError,
        recalculate_workbook,
    )

    project = _project_or_404(session, project_id)
    quote = session.scalar(
        select(QuoteVersion)
        .where(QuoteVersion.project_id == project.id, QuoteVersion.status == "submitted")
        .order_by(QuoteVersion.version_number.desc())
    )
    if quote is None:
        raise HTTPException(status_code=422, detail="제출 완료된 고객 견적 차수가 없습니다.")
    template = reference_material_path("SINGLEX_LGES_QUOTE_FORM_V5.20_20250529_EN.xlsx")
    if not template.is_file():
        raise HTTPException(status_code=422, detail="고객 견적 원본 양식을 찾을 수 없습니다.")
    generated_at = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{project.project_number}_고객견적_{quote.version_number}차_{generated_at}.xlsx"
    output = paths.exports / filename
    export_customer_quote(
        template,
        output,
        quote=quote,
        items=list(
            session.scalars(select(QuoteItem).where(QuoteItem.quote_version_id == quote.id))
        ),
    )
    try:
        recalculate_workbook(output)
    except SpreadsheetCalculationError as error:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(error)) from error
    return FileResponse(output, filename=output.name)


@router.post("/projects/{project_id}/packages")
def project_package_export(
    project_id: int, created_by: str = Form(), session: Session = Depends(get_session)
):
    package = export_project_package(
        session, project=_project_or_404(session, project_id), created_by=created_by
    )
    return FileResponse(package.stored_path, filename=Path(package.stored_path).name)


@router.post("/backups")
def local_backup() -> FileResponse:
    try:
        backup = create_local_backup()
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return FileResponse(backup, filename=backup.name)


@router.post("/backups/restore")
async def local_backup_restore(
    request: Request,
    backup_file: UploadFile = File(),
    confirmation: str = Form(),
):
    if not is_sqlite_database():
        raise HTTPException(
            status_code=409,
            detail="이 복원 기능은 로컬 SQLite 전용입니다. Supabase 복구 절차를 사용하세요.",
        )
    if confirmation != "RESTORE":
        raise HTTPException(status_code=422, detail="복원 확인 문구 RESTORE를 정확히 입력하세요.")
    if not backup_file.filename or Path(backup_file.filename).suffix.lower() != ".zip":
        raise HTTPException(status_code=422, detail="복원할 백업 ZIP 파일을 선택하세요.")
    temporary_path = paths.exports / f"restore_{uuid4().hex}.zip"
    temporary_path.write_bytes(await backup_file.read())
    try:
        pre_restore_backup = restore_local_backup(temporary_path)
    except (OSError, ValueError, RuntimeError) as error:
        raise HTTPException(status_code=422, detail=f"백업 복원 실패: {error}") from error
    finally:
        temporary_path.unlink(missing_ok=True)
    return templates.TemplateResponse(
        request,
        "operations/backup_restore.html",
        {"pre_restore_backup": pre_restore_backup.name},
    )


@router.post("/packages/inspect")
async def package_inspect(
    request: Request,
    package_file: UploadFile = File(),
    session: Session = Depends(get_session),
):
    if not package_file.filename or Path(package_file.filename).suffix.lower() != ".zip":
        raise HTTPException(status_code=422, detail="프로젝트 패키지 ZIP 파일을 선택하세요.")
    temporary_path = paths.exports / f"inspect_{uuid4().hex}.zip"
    temporary_path.write_bytes(await package_file.read())
    try:
        result = compare_project_package(session, package_path=temporary_path)
    except (OSError, ValueError, KeyError) as error:
        raise HTTPException(status_code=422, detail=f"패키지 확인 실패: {error}") from error
    return templates.TemplateResponse(request, "operations/package_inspect.html", result)


@router.post("/packages/import")
async def package_import(
    package_file: UploadFile = File(),
    imported_by: str = Form(),
    confirmation: str = Form(),
    session: Session = Depends(get_session),
):
    if confirmation != "IMPORT":
        raise HTTPException(
            status_code=422, detail="가져오기 확인 문구 IMPORT를 정확히 입력하세요."
        )
    if not package_file.filename or Path(package_file.filename).suffix.lower() != ".zip":
        raise HTTPException(status_code=422, detail="가져올 프로젝트 패키지 ZIP 파일을 선택하세요.")
    temporary_path = paths.exports / f"import_{uuid4().hex}.zip"
    temporary_path.write_bytes(await package_file.read())
    try:
        project = import_project_package(
            session, package_path=temporary_path, imported_by=imported_by
        )
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=422, detail=f"프로젝트 패키지 가져오기 실패: {error}"
        ) from error
    finally:
        temporary_path.unlink(missing_ok=True)
    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)
