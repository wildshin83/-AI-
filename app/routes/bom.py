"""BOM Rev 등록과 변경 비교 화면."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.bom import BomItem, BomRevision
from app.models.imports import UploadBatch
from app.models.project import Project
from app.services.bom import create_bom_revision, revision_changes

router = APIRouter(tags=["bom"])
templates = Jinja2Templates(directory="app/templates")


def project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    return project


@router.get("/projects/{project_id}/bom/new")
def bom_new_form(request: Request, project_id: int, session: Session = Depends(get_session)):
    project = project_or_404(session, project_id)
    uploads = list(
        session.scalars(
            select(UploadBatch).where(
                UploadBatch.project_id == project_id,
                UploadBatch.source_type == "inventor_bom",
                UploadBatch.status == "confirmed",
            )
        )
    )
    return templates.TemplateResponse(
        request, "bom/form.html", {"project": project, "uploads": uploads, "error": None}
    )


@router.post("/projects/{project_id}/bom")
def bom_create(
    request: Request,
    project_id: int,
    upload_batch_id: int = Form(),
    revision_name: str = Form(),
    memo: str = Form(""),
    session: Session = Depends(get_session),
):
    project = project_or_404(session, project_id)
    batch = session.get(UploadBatch, upload_batch_id)
    if batch is None or batch.project_id != project.id:
        raise HTTPException(status_code=404, detail="업로드 파일을 찾을 수 없습니다.")
    try:
        revision = create_bom_revision(
            session,
            project_id=project.id,
            upload_batch=batch,
            revision_name=revision_name,
            memo=memo,
        )
    except ValueError as error:
        uploads = list(
            session.scalars(
                select(UploadBatch).where(
                    UploadBatch.project_id == project_id,
                    UploadBatch.source_type == "inventor_bom",
                    UploadBatch.status == "confirmed",
                )
            )
        )
        return templates.TemplateResponse(
            request,
            "bom/form.html",
            {"project": project, "uploads": uploads, "error": str(error)},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return RedirectResponse(url=f"/bom/{revision.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/bom/{revision_id}")
def bom_detail(request: Request, revision_id: int, session: Session = Depends(get_session)):
    revision = session.get(BomRevision, revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="BOM Rev를 찾을 수 없습니다.")
    items = list(
        session.scalars(
            select(BomItem)
            .where(BomItem.bom_revision_id == revision.id)
            .order_by(BomItem.drawing_number)
        )
    )
    return templates.TemplateResponse(
        request,
        "bom/detail.html",
        {"revision": revision, "items": items, "changes": revision_changes(session, revision)},
    )
