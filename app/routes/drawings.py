"""도면 파일 업로드·열람 라우트."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.bom import BomItem, BomRevision
from app.models.drawings import DrawingFile
from app.models.project import Project
from app.services.drawings import register_drawing_file
from app.storage.drawings import store_drawing_upload

router = APIRouter(tags=["drawings"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/projects/{project_id}/drawings")
def drawing_list(request: Request, project_id: int, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    return templates.TemplateResponse(
        request,
        "drawings/list.html",
        {
            "project": project,
            "files": list(
                session.scalars(select(DrawingFile).where(DrawingFile.project_id == project.id))
            ),
            "items": list(
                session.scalars(
                    select(BomItem).join(BomRevision).where(BomRevision.project_id == project.id)
                )
            ),
            "revisions": list(
                session.scalars(select(BomRevision).where(BomRevision.project_id == project.id))
            ),
            "error": None,
        },
    )


@router.post("/projects/{project_id}/drawings")
async def drawing_upload(
    project_id: int,
    drawing_number: str = Form(),
    drawing_revision: str = Form(""),
    file_type: str = Form(),
    uploaded_by: str = Form(),
    memo: str = Form(""),
    bom_item_id: int | None = Form(None),
    bom_revision_id: int | None = Form(None),
    source_file: UploadFile = File(),
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    if project is None or not source_file.filename:
        raise HTTPException(status_code=404, detail="프로젝트 또는 업로드 파일을 확인하세요.")
    bom_item = session.get(BomItem, bom_item_id) if bom_item_id else None
    revision = session.get(BomRevision, bom_revision_id) if bom_revision_id else None
    item_revision = session.get(BomRevision, bom_item.bom_revision_id) if bom_item else None
    if (
        (revision and revision.project_id != project.id)
        or (item_revision and item_revision.project_id != project.id)
        or (bom_item and revision and bom_item.bom_revision_id != revision.id)
    ):
        raise HTTPException(status_code=422, detail="선택한 BOM 연결을 확인하세요.")
    try:
        stored_path = store_drawing_upload(
            project_id=project.id,
            original_file_name=source_file.filename,
            content=await source_file.read(),
        )
        register_drawing_file(
            session,
            project_id=project.id,
            bom_item=bom_item,
            bom_revision=revision,
            drawing_number=drawing_number,
            drawing_revision=drawing_revision,
            file_type=file_type,
            original_file_name=source_file.filename,
            stored_path=stored_path,
            mime_type=source_file.content_type,
            uploaded_by=uploaded_by,
            memo=memo,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return RedirectResponse(
        url=f"/projects/{project.id}/drawings", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/drawings/{drawing_file_id}/content")
def drawing_content(drawing_file_id: int, session: Session = Depends(get_session)):
    drawing = session.get(DrawingFile, drawing_file_id)
    if drawing is None or not Path(drawing.stored_path).is_file():
        raise HTTPException(status_code=404, detail="보관된 파일을 찾을 수 없습니다.")
    return FileResponse(
        drawing.stored_path, media_type=drawing.mime_type, filename=drawing.original_file_name
    )
