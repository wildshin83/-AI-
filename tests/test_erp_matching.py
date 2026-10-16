"""ERP 후보 우선순위와 사용자 확정 보호 규칙 회귀 테스트."""

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models.bom import BomItem, BomRevision
from app.models.erp import ERPTransaction
from app.models.imports import UploadBatch
from app.models.project import Project
from app.services.erp import confirm_erp_match, find_erp_candidates


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def build_item(session: Session, *, drawing_number: str = "AA-100-REV.A") -> BomItem:
    project = Project(
        project_number="ERP-001",
        project_name="ERP 검증",
        customer_name="고객사",
        equipment_unit="1호기",
        manager_name="담당자",
        status="견적",
    )
    upload = UploadBatch(
        project_id=1,
        source_type="inventor_bom",
        status="confirmed",
        original_file_name="bom.xlsx",
        stored_path="bom.xlsx",
        mapping={},
        issues=[],
    )
    session.add(project)
    session.flush()
    upload.project_id = project.id
    session.add(upload)
    session.flush()
    revision = BomRevision(project_id=project.id, upload_batch_id=upload.id, revision_name="A")
    session.add(revision)
    session.flush()
    item = BomItem(
        bom_revision_id=revision.id,
        drawing_number=drawing_number,
        normalized_drawing_number="AA100",
        specification="M8 X 20",
        quantity=1,
        source_data={},
    )
    session.add(item)
    session.flush()
    return item


def transaction(
    session: Session, item: BomItem, *, part_number: str, specification: str, updated: datetime
) -> ERPTransaction:
    erp = ERPTransaction(
        project_id=1,
        upload_batch_id=1,
        part_number=part_number,
        normalized_part_number="AA100" if part_number.startswith("AA") else "OTHER",
        specification=specification,
        normalized_specification=specification.replace(" ", "").upper(),
        erp_updated_at=updated,
        source_data={},
    )
    session.add(erp)
    session.flush()
    return erp


def test_drawing_candidates_take_precedence_over_specification(session: Session) -> None:
    item = build_item(session)
    transaction(
        session,
        item,
        part_number="OTHER-1",
        specification="M8 X 20",
        updated=datetime(2026, 9, 1),
    )
    matching = transaction(
        session,
        item,
        part_number="AA 100 R-A",
        specification="DIFFERENT",
        updated=datetime(2026, 9, 2),
    )

    candidates = find_erp_candidates(session, bom_item=item, as_of=date(2026, 10, 7))

    assert [(candidate.transaction.id, candidate.match_method) for candidate in candidates] == [
        (matching.id, "drawing_number")
    ]


def test_specification_is_used_only_when_no_drawing_candidate(session: Session) -> None:
    item = build_item(session)
    spec_match = transaction(
        session,
        item,
        part_number="OTHER-1",
        specification="M8 X 20",
        updated=datetime(2026, 9, 1),
    )

    candidates = find_erp_candidates(session, bom_item=item, as_of=date(2026, 10, 7))

    assert [(candidate.transaction.id, candidate.match_method) for candidate in candidates] == [
        (spec_match.id, "specification")
    ]


def test_match_requires_the_relevant_review_evidence(session: Session) -> None:
    item = build_item(session)
    erp = transaction(
        session,
        item,
        part_number="AA-100",
        specification="M8 X 20",
        updated=datetime(2026, 9, 1),
    )

    with pytest.raises(ValueError, match="필요한 확인 항목"):
        confirm_erp_match(
            session,
            bom_item=item,
            transaction=erp,
            match_method="drawing_number",
            review_type="purchased",
            review_evidence={"specification_checked": "확인"},
            confirmation_note="규격 확인",
            confirmed_by="홍길동",
        )

    match = confirm_erp_match(
        session,
        bom_item=item,
        transaction=erp,
        match_method="drawing_number",
        review_type="purchased",
        review_evidence={"specification_checked": "확인", "maker_checked": "확인"},
        confirmation_note="규격과 제조사 확인",
        confirmed_by="홍길동",
    )

    assert match.status == "applied"
    assert item.item_type == "purchased"
