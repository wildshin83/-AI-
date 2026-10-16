"""승인 전 원본 보존, 승인·충돌·롤백 검증."""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.project import Project
from app.models.schedules import ScheduleChangeRequest
from app.services.schedules import (
    ScheduleConflictError,
    ScheduleInput,
    ScheduleValidationError,
    review_schedule_request,
    submit_schedule_request,
    update_schedule,
)
from tests.test_user_management import identity


@pytest.fixture
def project(account_db):
    row = Project(
        project_number="TEST-SCHEDULE",
        project_name="Schedule test",
        customer_name="Test",
        equipment_unit="Test",
        manager_name="Test",
        target_delivery_date=date(2026, 11, 15),
    )
    account_db.add(row)
    account_db.commit()
    return row


def proposed(project, reason="고객 일정 변경", **kwargs):
    fields = dict(
        target_delivery_date=date(2026, 12, 1),
        incoming_date=date(2026, 11, 20),
        fob_date=None,
        base_version=project.schedule_version,
        reason=reason,
    )
    fields.update(kwargs)
    return ScheduleInput(**fields)


def test_request_does_not_modify_until_approved(account_db, accounts, project):
    pending = submit_schedule_request(
        account_db, actor=identity(accounts[0]), project_id=project.id, data=proposed(project)
    )
    assert project.target_delivery_date == date(2026, 11, 15)
    assert pending.status == "pending" and project.schedule_version == 1
    review_schedule_request(
        account_db, actor=identity(accounts[1]), request_id=pending.id, approve=True
    )
    assert project.target_delivery_date == date(2026, 12, 1)
    assert pending.status == "approved" and project.schedule_version == 2
    with pytest.raises(ScheduleConflictError):
        review_schedule_request(
            account_db, actor=identity(accounts[2]), request_id=pending.id, approve=True
        )


def test_duplicate_pending_and_member_write_are_denied(account_db, accounts, project):
    submit_schedule_request(
        account_db, actor=identity(accounts[0]), project_id=project.id, data=proposed(project)
    )
    with pytest.raises(ScheduleConflictError):
        submit_schedule_request(
            account_db, actor=identity(accounts[0]), project_id=project.id, data=proposed(project)
        )
    with pytest.raises(HTTPException):
        update_schedule(
            account_db, actor=identity(accounts[0]), project_id=project.id, data=proposed(project)
        )


@pytest.mark.parametrize("reason", [" ", "x" * 2001])
def test_invalid_reason_does_not_write(account_db, accounts, project, reason):
    with pytest.raises(ScheduleValidationError):
        update_schedule(
            account_db,
            actor=identity(accounts[2]),
            project_id=project.id,
            data=proposed(project, reason=reason),
        )
    assert project.schedule_version == 1


def test_rejection_preserves_dates(account_db, accounts, project):
    pending = submit_schedule_request(
        account_db, actor=identity(accounts[0]), project_id=project.id, data=proposed(project)
    )
    review_schedule_request(
        account_db,
        actor=identity(accounts[2]),
        request_id=pending.id,
        approve=False,
        comment="고객 확인 필요",
    )
    assert pending.status == "rejected" and project.schedule_version == 1


def test_direct_change_conflicts_pending_and_stale_editor(account_db, accounts, project):
    stale_data = proposed(project)
    pending = submit_schedule_request(
        account_db, actor=identity(accounts[0]), project_id=project.id, data=stale_data
    )
    update_schedule(
        account_db,
        actor=identity(accounts[1]),
        project_id=project.id,
        data=proposed(project, target_delivery_date=None),
    )
    assert project.target_delivery_date is None and pending.status == "conflicted"
    with pytest.raises(ScheduleConflictError):
        update_schedule(
            account_db, actor=identity(accounts[1]), project_id=project.id, data=stale_data
        )


def test_version_conflicts_even_when_dates_revert(account_db, accounts, project):
    stale = proposed(project)
    for value in (date(2026, 12, 1), date(2026, 11, 15)):
        update_schedule(
            account_db,
            actor=identity(accounts[2]),
            project_id=project.id,
            data=proposed(project, target_delivery_date=value),
        )
    with pytest.raises(ScheduleConflictError):
        update_schedule(account_db, actor=identity(accounts[2]), project_id=project.id, data=stale)


def test_audit_failure_rolls_back_dates(account_db, accounts, project, monkeypatch):
    import app.services.schedules as service

    def fail(*args, **kwargs):
        raise RuntimeError("test audit failure")

    monkeypatch.setattr(service, "record_audit", fail)
    with pytest.raises(RuntimeError):
        update_schedule(
            account_db, actor=identity(accounts[2]), project_id=project.id, data=proposed(project)
        )
    assert project.schedule_version == 1
    assert project.target_delivery_date == date(2026, 11, 15)
    assert account_db.scalar(select(AuditLog)) is None
    assert account_db.scalar(select(ScheduleChangeRequest)) is None
