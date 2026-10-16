"""고객 판매 견적의 차수 고정·금액 분리 규칙 회귀 테스트."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.domain.quote_compare import compare_quote_items
from app.models.bom import BomItem, BomRevision
from app.models.imports import UploadBatch
from app.models.project import Project
from app.models.quotes import QuoteItem
from app.services.quotes import (
    QuoteLockedError,
    create_quote_version,
    quote_totals,
    submit_quote,
    update_quote_item,
)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def bom_revision(session: Session) -> BomRevision:
    project = Project(
        project_number="QUOTE-001",
        project_name="견적 검증",
        customer_name="고객사",
        equipment_unit="1호기",
        manager_name="담당자",
        status="견적",
    )
    session.add(project)
    session.flush()
    upload = UploadBatch(
        project_id=project.id,
        source_type="inventor_bom",
        status="confirmed",
        original_file_name="bom.xlsx",
        stored_path="bom.xlsx",
        mapping={},
        issues=[],
    )
    session.add(upload)
    session.flush()
    revision = BomRevision(project_id=project.id, upload_batch_id=upload.id, revision_name="A")
    session.add(revision)
    session.flush()
    session.add(
        BomItem(
            bom_revision_id=revision.id,
            drawing_number="M-01",
            normalized_drawing_number="M01",
            component="가공품",
            quantity=Decimal("2"),
            source_data={},
        )
    )
    session.flush()
    return revision


def test_submitted_quote_is_locked_and_preserves_customer_amount(session: Session) -> None:
    revision = bom_revision(session)
    quote = create_quote_version(
        session, project_id=revision.project_id, bom_revision=revision, created_by="담당자"
    )
    quote_item = session.scalar(select(QuoteItem).where(QuoteItem.quote_version_id == quote.id))
    assert quote_item is not None
    update_quote_item(
        session,
        quote=quote,
        quote_item=quote_item,
        item_type="machined",
        material_cost=Decimal("100"),
        machining_cost=Decimal("50"),
        treatment_cost=Decimal("10"),
        purchased_unit_price=Decimal("0"),
        memo="고객 견적 배분",
    )

    assert quote_totals(session, quote).grand_total == Decimal("320")
    submit_quote(session, quote=quote, submission_note="1차 고객 제출")

    with pytest.raises(QuoteLockedError):
        update_quote_item(
            session,
            quote=quote,
            quote_item=quote_item,
            item_type="purchased",
            material_cost=Decimal("0"),
            machining_cost=Decimal("0"),
            treatment_cost=Decimal("0"),
            purchased_unit_price=Decimal("200"),
            memo=None,
        )


def test_quote_comparison_reports_customer_amount_changes(session: Session) -> None:
    revision = bom_revision(session)
    first_quote = create_quote_version(
        session, project_id=revision.project_id, bom_revision=revision, created_by="담당자"
    )
    second_quote = create_quote_version(
        session, project_id=revision.project_id, bom_revision=revision, created_by="담당자"
    )
    first_item = session.scalar(
        select(QuoteItem).where(QuoteItem.quote_version_id == first_quote.id)
    )
    second_item = session.scalar(
        select(QuoteItem).where(QuoteItem.quote_version_id == second_quote.id)
    )
    assert first_item is not None and second_item is not None
    update_quote_item(
        session,
        quote=first_quote,
        quote_item=first_item,
        item_type="purchased",
        material_cost=Decimal("0"),
        machining_cost=Decimal("0"),
        treatment_cost=Decimal("0"),
        purchased_unit_price=Decimal("100"),
        memo=None,
    )
    update_quote_item(
        session,
        quote=second_quote,
        quote_item=second_item,
        item_type="purchased",
        material_cost=Decimal("0"),
        machining_cost=Decimal("0"),
        treatment_cost=Decimal("0"),
        purchased_unit_price=Decimal("120"),
        memo=None,
    )

    changes = compare_quote_items([first_item], [second_item])

    assert [
        (change.change_type, change.before_amount, change.after_amount) for change in changes
    ] == [("변경", Decimal("200"), Decimal("240"))]
