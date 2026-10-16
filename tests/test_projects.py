"""프로젝트 등록·보관과 감사 이력의 회귀 테스트."""

from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models.audit import AuditLog
from app.services.projects import (
    ProjectCreateInput,
    ProjectNumberAlreadyExistsError,
    create_project,
    list_projects,
    set_project_archived,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def project_input(project_number: str = "TEST-001") -> ProjectCreateInput:
    return ProjectCreateInput(
        project_number=project_number,
        project_name="검증 프로젝트",
        customer_name="테스트 고객사",
        equipment_unit="검증 1호기",
        manager_name="테스트 담당",
        status="견적",
        target_delivery_date=date(2026, 11, 1),
    )


def test_create_project_records_audit_log(session: Session) -> None:
    project = create_project(session, project_input())

    audit_log = session.scalar(select(AuditLog))

    assert project.id is not None
    assert project.project_number == "TEST-001"
    assert audit_log is not None
    assert audit_log.action == "project.created"
    assert audit_log.entity_id == str(project.id)


def test_project_creates_three_schedule_dates(session: Session):
    data = replace(project_input(), incoming_date=date(2026, 10, 20), fob_date=date(2026, 10, 25))
    project = create_project(session, data)
    assert project.incoming_date == date(2026, 10, 20)
    assert project.fob_date == date(2026, 10, 25)
    assert project.schedule_version == 1


def test_duplicate_project_number_is_rejected(session: Session) -> None:
    create_project(session, project_input())

    with pytest.raises(ProjectNumberAlreadyExistsError):
        create_project(session, project_input())


def test_archived_project_is_hidden_from_default_list(session: Session) -> None:
    project = create_project(session, project_input())

    set_project_archived(session, project, archived=True)

    assert list_projects(session, include_archived=False) == []
    assert list_projects(session, include_archived=True) == [project]
    audit_actions = list(session.scalars(select(AuditLog.action)))
    assert set(audit_actions) == {"project.created", "project.archived"}
