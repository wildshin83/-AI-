"""명시적으로 제공된 테스트 PostgreSQL에서만 실제 행 잠금을 검증한다."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.db import Base
from app.models.auth import AuthUser
from app.models.project import Project
from app.models.schedules import ScheduleChangeRequest
from app.services.schedules import (
    ScheduleConflictError,
    ScheduleInput,
    review_schedule_request,
    submit_schedule_request,
    update_schedule,
)
from tests.test_user_management import identity


@pytest.fixture
def postgres_case():
    url = os.getenv("BOM_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("별도 PostgreSQL 테스트 URL이 없어 실제 동시성 검증 미실행")
    from app.db import _normalize_database_url

    schema = "test_schedules_" + uuid4().hex
    engine = create_engine(
        _normalize_database_url(url),
        connect_args={"prepare_threshold": None, "connect_timeout": 10},
    )
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated) as session:
            users = [
                AuthUser(
                    email=f"u{i}@example.test",
                    display_name=f"u{i}",
                    password_hash="unused",
                    permission_level=1 if i == 0 else 2,
                    must_change_password=False,
                )
                for i in range(3)
            ]
            project = Project(
                project_number="PG-TEST",
                project_name="Test",
                customer_name="Test",
                equipment_unit="Test",
                manager_name="Test",
            )
            session.add_all([*users, project])
            session.commit()
            actors = [identity(user) for user in users]
            project_id = project.id
        yield isolated, actors, project_id
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def _data():
    return ScheduleInput(date(2026, 12, 1), None, None, 1, "동시 변경 검증")


def _race(engine, operations):
    barrier = Barrier(2)

    def run(operation):
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                operation(session)
                return "saved"
            except ScheduleConflictError:
                return "conflict"

    with ThreadPoolExecutor(2) as pool:
        return list(pool.map(run, operations))


def test_concurrent_submissions_create_only_one_pending(postgres_case):
    engine, actors, project_id = postgres_case

    def submit(session):
        submit_schedule_request(session, actor=actors[0], project_id=project_id, data=_data())

    assert sorted(_race(engine, [submit, submit])) == ["conflict", "saved"]
    with Session(engine) as session:
        assert len(list(session.scalars(select(ScheduleChangeRequest)))) == 1


@pytest.mark.parametrize("direct", [False, True])
def test_approval_race_changes_schedule_only_once(postgres_case, direct):
    engine, actors, project_id = postgres_case
    with Session(engine) as session:
        pending = submit_schedule_request(
            session, actor=actors[0], project_id=project_id, data=_data()
        )
        request_id = pending.id

    def approve(session):
        review_schedule_request(session, actor=actors[1], request_id=request_id, approve=True)

    def other(session):
        if direct:
            update_schedule(session, actor=actors[2], project_id=project_id, data=_data())
        else:
            review_schedule_request(session, actor=actors[2], request_id=request_id, approve=True)

    assert sorted(_race(engine, [approve, other])) == ["conflict", "saved"]
    with Session(engine) as session:
        assert session.get(Project, project_id).schedule_version == 2
