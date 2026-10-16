"""고객 판매 견적의 차수 작성과 제출 고정 화면."""

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.quote_calculation import customer_item_amount, customer_unit_price
from app.domain.quote_compare import compare_quote_items
from app.models.bom import BomRevision
from app.models.project import Project
from app.models.quotes import QuoteAdjustment, QuoteItem, QuoteVersion
from app.services.quotes import (
    QuoteLockedError,
    add_quote_adjustment,
    create_quote_version,
    quote_totals,
    submit_quote,
    update_quote_item,
)

router = APIRouter(tags=["quotes"])
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["customer_unit_price"] = customer_unit_price
templates.env.globals["customer_item_amount"] = customer_item_amount


def _project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    return project


def _quote_context(session: Session, quote_id: int) -> dict[str, object]:
    quote = session.get(QuoteVersion, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="견적 차수를 찾을 수 없습니다.")
    return {
        "quote": quote,
        "project": _project_or_404(session, quote.project_id),
        "items": list(
            session.scalars(
                select(QuoteItem)
                .where(QuoteItem.quote_version_id == quote.id)
                .order_by(QuoteItem.drawing_number)
            )
        ),
        "adjustments": list(
            session.scalars(
                select(QuoteAdjustment).where(QuoteAdjustment.quote_version_id == quote.id)
            )
        ),
        "totals": quote_totals(session, quote),
    }


def _decimal(value: str) -> Decimal:
    try:
        return Decimal(value or "0")
    except InvalidOperation as error:
        raise ValueError("금액은 숫자로 입력하세요.") from error


@router.get("/projects/{project_id}/quotes/new")
def quote_new_form(request: Request, project_id: int, session: Session = Depends(get_session)):
    project = _project_or_404(session, project_id)
    revisions = list(
        session.scalars(
            select(BomRevision)
            .where(BomRevision.project_id == project.id)
            .order_by(BomRevision.id.desc())
        )
    )
    return templates.TemplateResponse(
        request, "quotes/form.html", {"project": project, "revisions": revisions, "error": None}
    )


@router.post("/projects/{project_id}/quotes")
def quote_create(
    request: Request,
    project_id: int,
    bom_revision_id: int = Form(),
    created_by: str = Form(),
    session: Session = Depends(get_session),
):
    project = _project_or_404(session, project_id)
    revision = session.get(BomRevision, bom_revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="BOM Rev를 찾을 수 없습니다.")
    try:
        quote = create_quote_version(
            session, project_id=project.id, bom_revision=revision, created_by=created_by
        )
    except ValueError as error:
        return templates.TemplateResponse(
            request,
            "quotes/form.html",
            {"project": project, "revisions": [revision], "error": str(error)},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return RedirectResponse(url=f"/quotes/{quote.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/quotes/{quote_id}")
def quote_detail(request: Request, quote_id: int, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request, "quotes/detail.html", _quote_context(session, quote_id)
    )


@router.post("/quotes/{quote_id}/adjustments")
def quote_adjustment_add(
    quote_id: int,
    name: str = Form(),
    amount: str = Form(),
    memo: str = Form(""),
    session: Session = Depends(get_session),
):
    quote = session.get(QuoteVersion, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="견적 차수를 찾을 수 없습니다.")
    try:
        add_quote_adjustment(session, quote=quote, name=name, amount=_decimal(amount), memo=memo)
    except (ValueError, QuoteLockedError):
        return RedirectResponse(url=f"/quotes/{quote_id}", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/quotes/{quote_id}/compare/{base_quote_id}")
def quote_compare(
    request: Request, quote_id: int, base_quote_id: int, session: Session = Depends(get_session)
):
    context = _quote_context(session, quote_id)
    base = _quote_context(session, base_quote_id)
    context["base_quote"] = base["quote"]
    context["changes"] = compare_quote_items(base["items"], context["items"])
    return templates.TemplateResponse(request, "quotes/compare.html", context)


@router.post("/quotes/{quote_id}/items/{item_id}")
def quote_item_update(
    request: Request,
    quote_id: int,
    item_id: int,
    item_type: str = Form(),
    material_cost: str = Form("0"),
    machining_cost: str = Form("0"),
    treatment_cost: str = Form("0"),
    purchased_unit_price: str = Form("0"),
    memo: str = Form(""),
    session: Session = Depends(get_session),
):
    quote = session.get(QuoteVersion, quote_id)
    quote_item = session.get(QuoteItem, item_id)
    if quote is None or quote_item is None:
        raise HTTPException(status_code=404, detail="견적 정보를 찾을 수 없습니다.")
    try:
        update_quote_item(
            session,
            quote=quote,
            quote_item=quote_item,
            item_type=item_type,
            material_cost=_decimal(material_cost),
            machining_cost=_decimal(machining_cost),
            treatment_cost=_decimal(treatment_cost),
            purchased_unit_price=_decimal(purchased_unit_price),
            memo=memo,
        )
    except (ValueError, QuoteLockedError) as error:
        context = _quote_context(session, quote_id)
        context["error"] = str(error)
        return templates.TemplateResponse(
            request, "quotes/detail.html", context, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/quotes/{quote_id}/submit")
def quote_submit(
    request: Request,
    quote_id: int,
    submission_note: str = Form(),
    session: Session = Depends(get_session),
):
    quote = session.get(QuoteVersion, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="견적 차수를 찾을 수 없습니다.")
    try:
        submit_quote(session, quote=quote, submission_note=submission_note)
    except (ValueError, QuoteLockedError) as error:
        context = _quote_context(session, quote_id)
        context["error"] = str(error)
        return templates.TemplateResponse(
            request, "quotes/detail.html", context, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=status.HTTP_303_SEE_OTHER)
