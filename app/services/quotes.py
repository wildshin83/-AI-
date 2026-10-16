"""견적 차수 생성·수정·제출 고정과 내부 단가 확정 유스케이스."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.quote_calculation import customer_item_amount
from app.models.alerts import PriceRecord
from app.models.bom import BomItem, BomRevision
from app.models.quotes import QuoteAdjustment, QuoteItem, QuoteVersion
from app.services.audit import record_audit


class QuoteLockedError(ValueError):
    """제출 완료 견적을 수정하려 할 때 발생한다."""


@dataclass(frozen=True)
class QuoteTotals:
    item_total: Decimal
    adjustment_total: Decimal
    grand_total: Decimal


def create_quote_version(
    session: Session,
    *,
    project_id: int,
    bom_revision: BomRevision,
    created_by: str,
) -> QuoteVersion:
    """BOM Rev를 복제하여 다음 작성 중 견적 차수를 만든다."""

    if bom_revision.project_id != project_id:
        raise ValueError("프로젝트의 BOM Rev만 견적 기준으로 선택할 수 있습니다.")
    if not created_by.strip():
        raise ValueError("견적 작성자는 필수입니다.")
    next_number = (
        session.scalar(
            select(func.max(QuoteVersion.version_number)).where(
                QuoteVersion.project_id == project_id
            )
        )
        or 0
    ) + 1
    quote = QuoteVersion(
        project_id=project_id,
        bom_revision_id=bom_revision.id,
        version_number=next_number,
        created_by=created_by.strip(),
    )
    session.add(quote)
    session.flush()
    for item in session.scalars(
        select(BomItem)
        .where(BomItem.bom_revision_id == bom_revision.id)
        .order_by(BomItem.drawing_number)
    ):
        session.add(
            QuoteItem(
                quote_version_id=quote.id,
                bom_item_id=item.id,
                drawing_number=item.drawing_number,
                item_name=item.component or item.title,
                item_type=item.item_type,
                material=item.material,
                treatment=item.treatment,
                specification=item.specification,
                maker=item.maker,
                quantity=item.quantity,
            )
        )
    record_audit(
        session,
        action="quote_version.created",
        entity_type="quote_version",
        entity_id=quote.id,
        actor_name=created_by.strip(),
        details={"project_id": project_id, "bom_revision_id": bom_revision.id},
    )
    session.commit()
    session.refresh(quote)
    return quote


def _require_draft(quote: QuoteVersion) -> None:
    if quote.status != "draft":
        raise QuoteLockedError("제출 완료된 견적은 수정할 수 없습니다. 다음 견적 차수를 만드세요.")


def update_quote_item(
    session: Session,
    *,
    quote: QuoteVersion,
    quote_item: QuoteItem,
    item_type: str,
    material_cost: Decimal,
    machining_cost: Decimal,
    treatment_cost: Decimal,
    purchased_unit_price: Decimal,
    memo: str | None,
) -> QuoteItem:
    """작성 중 견적의 고객 판매 견적단가만 수정한다."""

    _require_draft(quote)
    if quote_item.quote_version_id != quote.id:
        raise ValueError("선택한 견적 품목이 해당 견적 차수에 속하지 않습니다.")
    if item_type not in {"machined", "purchased"}:
        raise ValueError("가공품 또는 구매품을 선택하세요.")
    if min(material_cost, machining_cost, treatment_cost, purchased_unit_price) < 0:
        raise ValueError("판매 견적단가는 음수가 될 수 없습니다.")
    quote_item.item_type = item_type
    quote_item.material_cost = material_cost
    quote_item.machining_cost = machining_cost
    quote_item.treatment_cost = treatment_cost
    quote_item.purchased_unit_price = purchased_unit_price
    quote_item.memo = memo.strip() if memo else None
    record_audit(
        session,
        action="quote_item.updated",
        entity_type="quote_item",
        entity_id=quote_item.id,
        details={"quote_version_id": quote.id},
    )
    session.commit()
    return quote_item


def quote_totals(session: Session, quote: QuoteVersion) -> QuoteTotals:
    items = list(session.scalars(select(QuoteItem).where(QuoteItem.quote_version_id == quote.id)))
    adjustments = list(
        session.scalars(select(QuoteAdjustment).where(QuoteAdjustment.quote_version_id == quote.id))
    )
    item_total = sum((customer_item_amount(item) for item in items), Decimal("0"))
    adjustment_total = sum((adjustment.amount for adjustment in adjustments), Decimal("0"))
    return QuoteTotals(item_total, adjustment_total, item_total + adjustment_total)


def add_quote_adjustment(
    session: Session,
    *,
    quote: QuoteVersion,
    name: str,
    amount: Decimal,
    memo: str | None,
) -> QuoteAdjustment:
    """이윤·일반관리비 등 품목 외 고객 견적 항목을 작성 중 차수에 추가한다."""

    _require_draft(quote)
    if not name.strip():
        raise ValueError("부대 항목명은 필수입니다.")
    adjustment = QuoteAdjustment(
        quote_version_id=quote.id,
        name=name.strip(),
        amount=amount,
        memo=memo.strip() if memo else None,
    )
    session.add(adjustment)
    session.flush()
    record_audit(
        session,
        action="quote_adjustment.added",
        entity_type="quote_adjustment",
        entity_id=adjustment.id,
        details={"quote_version_id": quote.id},
    )
    session.commit()
    return adjustment


def submit_quote(session: Session, *, quote: QuoteVersion, submission_note: str) -> QuoteVersion:
    """제출 시점에 견적 차수를 잠그고 그 상태를 보존한다."""

    _require_draft(quote)
    if not submission_note.strip():
        raise ValueError("제출 메모는 필수입니다.")
    quote.status = "submitted"
    quote.submission_date = datetime.now()
    quote.submission_note = submission_note.strip()
    record_audit(
        session,
        action="quote_version.submitted",
        entity_type="quote_version",
        entity_id=quote.id,
        details={"bom_revision_id": quote.bom_revision_id},
    )
    session.commit()
    return quote


def confirm_internal_price(
    session: Session,
    *,
    bom_item: BomItem,
    amount: Decimal,
    confirmed_by: str,
    memo: str,
) -> PriceRecord:
    """내부 관리단가를 별도 이력으로 확정하며 판매 견적에는 영향을 주지 않는다."""

    if amount < 0 or not confirmed_by.strip() or not memo.strip():
        raise ValueError("내부 관리단가, 확정자, 근거 메모를 확인하세요.")
    record = PriceRecord(
        bom_item_id=bom_item.id,
        price_type="internal_management",
        amount=amount,
        is_confirmed=True,
        confirmed_by=confirmed_by.strip(),
        confirmed_at=datetime.now(),
        memo=memo.strip(),
    )
    session.add(record)
    session.flush()
    record_audit(
        session,
        action="internal_price.confirmed",
        entity_type="price_record",
        entity_id=record.id,
        actor_name=confirmed_by.strip(),
        details={"bom_item_id": bom_item.id},
    )
    session.commit()
    return record
