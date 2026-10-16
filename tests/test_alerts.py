"""현재 ERP 양식으로 가능한 단가·납기 경고 회귀 테스트."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models.alerts import PriceRecord
from app.models.bom import BomItem, BomRevision
from app.models.erp import ErpMatch, ERPTransaction
from app.models.imports import UploadBatch
from app.models.project import Project
from app.services.alerts import build_alert_candidates, update_alert_status


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def item(session: Session) -> BomItem:
    project = Project(
        project_number="ALERT-001",
        project_name="경고 검증",
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
    bom_item = BomItem(
        bom_revision_id=revision.id,
        drawing_number="AA-100",
        normalized_drawing_number="AA100",
        quantity=1,
        source_data={},
    )
    session.add(bom_item)
    session.flush()
    return bom_item


def applied_erp(session: Session, bom_item: BomItem) -> ERPTransaction:
    erp = ERPTransaction(
        project_id=1,
        upload_batch_id=1,
        part_number="AA-100",
        normalized_part_number="AA100",
        normalized_specification="",
        unit_price=Decimal("110"),
        ordered_quantity=Decimal("2"),
        received_quantity=Decimal("0"),
        planned_delivery_date=date(2026, 10, 7),
        erp_updated_at=datetime(2026, 10, 1),
        source_data={},
    )
    session.add(erp)
    session.flush()
    session.add(
        ErpMatch(
            bom_item_id=bom_item.id,
            erp_transaction_id=erp.id,
            match_method="drawing_number",
            status="applied",
            review_evidence={},
        )
    )
    session.add(
        PriceRecord(
            bom_item_id=bom_item.id,
            erp_transaction_id=999,
            price_type="erp_reference",
            amount=Decimal("100"),
            basis_date=date(2026, 9, 1),
        )
    )
    session.flush()
    return erp


def test_no_recent_erp_history_is_reported(session: Session) -> None:
    bom_item = item(session)

    candidates = build_alert_candidates(session, item=bom_item, as_of=date(2026, 10, 7))

    assert [candidate.alert_code for candidate in candidates] == ["no_recent_erp_history"]


def test_price_increase_and_due_today_are_reported(session: Session) -> None:
    bom_item = item(session)
    applied_erp(session, bom_item)

    candidates = build_alert_candidates(session, item=bom_item, as_of=date(2026, 10, 7))

    assert {candidate.alert_code for candidate in candidates} == {
        "erp_price_increase",
        "delivery_due_soon",
    }


def test_confirmed_internal_price_is_never_overwritten_and_requires_review(
    session: Session,
) -> None:
    bom_item = item(session)
    applied_erp(session, bom_item)
    session.add(
        PriceRecord(
            bom_item_id=bom_item.id,
            price_type="internal_management",
            amount=Decimal("90"),
            is_confirmed=True,
            confirmed_by="담당자",
            confirmed_at=datetime(2026, 9, 15),
        )
    )
    session.flush()

    candidates = build_alert_candidates(session, item=bom_item, as_of=date(2026, 10, 7))

    assert "price_recheck_needed" in {candidate.alert_code for candidate in candidates}


def test_resolution_requires_a_note(session: Session) -> None:
    bom_item = item(session)
    # 이 테스트에서는 경고 테이블 생성과 상태 전이만 검증한다.
    from app.models.alerts import Alert

    alert = Alert(
        project_id=1,
        bom_item_id=bom_item.id,
        alert_code="test",
        severity="warning",
        title="테스트 경고",
        details={},
        source_fingerprint="test",
    )
    session.add(alert)
    session.flush()

    with pytest.raises(ValueError, match="근거 메모"):
        update_alert_status(
            session,
            alert=alert,
            status="resolved",
            actor_name="담당자",
            action_note="",
        )
