"""Excel 업로드 미리보기와 매핑 확정 라우트."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_session
from app.importers.excel_mapping import WorkbookKind, rules_for
from app.models.imports import UploadBatch
from app.models.project import Project
from app.services.imports import confirm_batch, create_preview_batch
from app.storage.uploads import store_excel_upload

router = APIRouter(tags=["uploads"])
templates = Jinja2Templates(directory="app/templates")


def _project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    return project


def _batch_or_404(session: Session, batch_id: int) -> UploadBatch:
    batch = session.get(UploadBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="업로드 정보를 찾을 수 없습니다.")
    return batch


@router.get("/projects/{project_id}/uploads/new")
def upload_form(request: Request, project_id: int, session: Session = Depends(get_session)):
    project = _project_or_404(session, project_id)
    return templates.TemplateResponse(
        request, "uploads/form.html", {"project": project, "error": None}
    )


@router.post("/projects/{project_id}/uploads/preview")
async def upload_preview(
    request: Request,
    project_id: int,
    source_type: WorkbookKind = Form(),
    source_file: UploadFile = File(),
    session: Session = Depends(get_session),
):
    project = _project_or_404(session, project_id)
    if not source_file.filename:
        return templates.TemplateResponse(
            request,
            "uploads/form.html",
            {"project": project, "error": "업로드할 Excel 파일을 선택하세요."},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    try:
        stored_path = store_excel_upload(
            project_id=project.id,
            original_file_name=source_file.filename,
            content=await source_file.read(),
        )
        batch, preview = create_preview_batch(
            session,
            project_id=project.id,
            source_type=source_type,
            original_file_name=source_file.filename,
            stored_path=stored_path,
        )
    except (ValueError, OSError) as error:
        return templates.TemplateResponse(
            request,
            "uploads/form.html",
            {"project": project, "error": str(error)},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return templates.TemplateResponse(
        request,
        "uploads/preview.html",
        {
            "project": project,
            "batch": batch,
            "headers": preview.unmapped_headers + list(preview.mapping.values()),
            "rules": rules_for(source_type),
            "mapping": preview.mapping,
            "issues": preview.issues,
            "error": None,
        },
    )


@router.post("/uploads/{batch_id}/confirm")
async def upload_confirm(
    request: Request,
    batch_id: int,
    session: Session = Depends(get_session),
):
    batch = _batch_or_404(session, batch_id)
    project = _project_or_404(session, batch.project_id)
    form = await request.form()
    mapping = {
        rule.field: str(form.get(f"mapping_{rule.field}", "")).strip()
        for rule in rules_for(WorkbookKind(batch.source_type))
    }
    errors = confirm_batch(session, batch=batch, mapping=mapping)
    if errors:
        headers = list(dict.fromkeys(list(batch.mapping.values()) + list(mapping.values())))
        return templates.TemplateResponse(
            request,
            "uploads/preview.html",
            {
                "project": project,
                "batch": batch,
                "headers": [header for header in headers if header],
                "rules": rules_for(WorkbookKind(batch.source_type)),
                "mapping": mapping,
                "issues": [],
                "error": " ".join(errors),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return RedirectResponse(url=f"/projects/{project.id}", status_code=status.HTTP_303_SEE_OTHER)
