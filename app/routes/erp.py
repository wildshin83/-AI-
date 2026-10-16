"""ERP 이력 등록과 BOM 품목별 후보 검토 화면."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.part_matching import normalize_drawing_number
from app.models.bom import BomItem, BomRevision
from app.models.erp import ErpMatch, ERPTransaction
from app.models.imports import UploadBatch
from app.models.project import Project
from app.services.alerts import refresh_project_alerts
from app.services.erp import (
    ErpCandidate,
    ErpImportAlreadyExistsError,
    confirm_erp_match,
    find_erp_candidates,
    import_erp_transactions,
)

router = APIRouter(tags=["erp"])
templates = Jinja2Templates(directory="app/templates")


def _project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    return project


def _bom_item_or_404(session: Session, item_id: int) -> BomItem:
    item = session.get(BomItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="BOM 품목을 찾을 수 없습니다.")
    return item


@router.get("/projects/{project_id}/erp/new")
def erp_import_form(request: Request, project_id: int, session: Session = Depends(get_session)):
    project = _project_or_404(session, project_id)
    uploads = list(
        session.scalars(
            select(UploadBatch).where(
                UploadBatch.project_id == project.id,
                UploadBatch.source_type == "erp_bom",
                UploadBatch.status == "confirmed",
            )
        )
    )
    imported_ids = set(
        session.scalars(
            select(ERPTransaction.upload_batch_id).where(ERPTransaction.project_id == project.id)
        )
    )
    return templates.TemplateResponse(
        request,
        "erp/import_form.html",
        {"project": project, "uploads": uploads, "imported_ids": imported_ids, "error": None},
    )


@router.post("/projects/{project_id}/erp")
def erp_import(
    request: Request,
    project_id: int,
    upload_batch_id: int = Form(),
    session: Session = Depends(get_session),
):
    project = _project_or_404(session, project_id)
    batch = session.get(UploadBatch, upload_batch_id)
    if batch is None or batch.project_id != project.id:
        raise HTTPException(status_code=404, detail="업로드 파일을 찾을 수 없습니다.")
    try:
        import_erp_transactions(session, upload_batch=batch)
        refresh_project_alerts(session, project_id=project.id)
    except (ValueError, ErpImportAlreadyExistsError) as error:
        uploads = list(
            session.scalars(
                select(UploadBatch).where(
                    UploadBatch.project_id == project.id,
                    UploadBatch.source_type == "erp_bom",
                    UploadBatch.status == "confirmed",
                )
            )
        )
        imported_ids = set(
            session.scalars(
                select(ERPTransaction.upload_batch_id).where(
                    ERPTransaction.project_id == project.id
                )
            )
        )
        return templates.TemplateResponse(
            request,
            "erp/import_form.html",
            {
                "project": project,
                "uploads": uploads,
                "imported_ids": imported_ids,
                "error": str(error),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return RedirectResponse(url=f"/projects/{project.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/bom/items/{item_id}/erp-candidates")
def erp_candidates(
    request: Request,
    item_id: int,
    manual_part_number: str = "",
    session: Session = Depends(get_session),
):
    item = _bom_item_or_404(session, item_id)
    revision = session.get(BomRevision, item.bom_revision_id)
    candidates = find_erp_candidates(session, bom_item=item)
    if manual_part_number.strip():
        normalized = normalize_drawing_number(manual_part_number)
        candidates = [
            candidate
            for candidate in candidates
            if candidate.transaction.normalized_part_number == normalized
        ]
        if not candidates:
            candidates = [
                ErpCandidate(transaction, "manual")
                for transaction in session.scalars(
                    select(ERPTransaction)
                    .where(
                        ERPTransaction.project_id == revision.project_id,
                        ERPTransaction.normalized_part_number == normalized,
                    )
                    .order_by(ERPTransaction.erp_updated_at.desc(), ERPTransaction.id.desc())
                )
            ]
    applied_match = session.scalar(
        select(ErpMatch)
        .where(ErpMatch.bom_item_id == item.id, ErpMatch.status == "applied")
        .order_by(ErpMatch.confirmed_at.desc())
    )
    applied_transaction = (
        session.get(ERPTransaction, applied_match.erp_transaction_id) if applied_match else None
    )
    return templates.TemplateResponse(
        request,
        "erp/candidates.html",
        {
            "item": item,
            "revision": revision,
            "candidates": candidates,
            "applied_match": applied_match,
            "applied_transaction": applied_transaction,
            "manual_part_number": manual_part_number,
            "error": None,
        },
    )


@router.post("/bom/items/{item_id}/erp-candidates/{transaction_id}/confirm")
def erp_candidate_confirm(
    request: Request,
    item_id: int,
    transaction_id: int,
    match_method: str = Form(),
    review_type: str = Form(),
    shape_dimension_checked: str | None = Form(None),
    material_checked: str | None = Form(None),
    treatment_checked: str | None = Form(None),
    quantity_checked: str | None = Form(None),
    specification_checked: str | None = Form(None),
    maker_checked: str | None = Form(None),
    confirmation_note: str = Form(),
    confirmed_by: str = Form(),
    session: Session = Depends(get_session),
):
    item = _bom_item_or_404(session, item_id)
    transaction = session.get(ERPTransaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="ERP 이력을 찾을 수 없습니다.")
    revision = session.get(BomRevision, item.bom_revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="BOM Rev를 찾을 수 없습니다.")
    evidence = {
        "shape_dimension_checked": shape_dimension_checked or "",
        "material_checked": material_checked or "",
        "treatment_checked": treatment_checked or "",
        "quantity_checked": quantity_checked or "",
        "specification_checked": specification_checked or "",
        "maker_checked": maker_checked or "",
    }
    try:
        confirm_erp_match(
            session,
            bom_item=item,
            transaction=transaction,
            match_method=match_method,
            review_type=review_type,
            review_evidence=evidence,
            confirmation_note=confirmation_note,
            confirmed_by=confirmed_by,
        )
        refresh_project_alerts(session, project_id=revision.project_id)
    except ValueError as error:
        return templates.TemplateResponse(
            request,
            "erp/candidates.html",
            {
                "item": item,
                "revision": revision,
                "candidates": find_erp_candidates(session, bom_item=item),
                "applied_match": None,
                "applied_transaction": None,
                "manual_part_number": "",
                "error": str(error),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return RedirectResponse(
        url=f"/bom/items/{item.id}/erp-candidates", status_code=status.HTTP_303_SEE_OTHER
    )
