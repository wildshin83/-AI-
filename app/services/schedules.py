"""프로젝트 일정 변경과 승인 규칙. 잠금 순서는 사용자→프로젝트→요청이다."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.schedules import ScheduleChangeRequest
from app.security import SessionUser, require_current_user
from app.services.audit import record_audit
from app.services.transactions import commit_or_rollback

DATE_FIELDS = ("target_delivery_date", "incoming_date", "fob_date")
STATUS_LABELS = {
    "pending": "승인 대기",
    "approved": "승인",
    "rejected": "반려",
    "conflicted": "재요청 필요",
}


class ScheduleValidationError(ValueError):
    """입력 일정·사유가 올바르지 않다."""


class ScheduleConflictError(ValueError):
    """이전 화면이나 중복 요청이 최신 일정을 덮지 않게 한다."""


@dataclass(frozen=True)
class ScheduleInput:
    target_delivery_date: date | None
    incoming_date: date | None
    fob_date: date | None
    base_version: int
    reason: str


def schedule_values(source) -> dict:
    return {field: getattr(source, field) for field in DATE_FIELDS}


def _snapshot(source) -> dict:
    return {
        field: value.isoformat() if value else None
        for field, value in schedule_values(source).items()
    }


def _project(session, project_id):
    project = session.scalar(
        select(Project)
        .where(Project.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not project:
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다.")
    return project


def _pending(session, project_id):
    return session.scalar(
        select(ScheduleChangeRequest)
        .where(
            ScheduleChangeRequest.project_id == project_id,
            ScheduleChangeRequest.status == "pending",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _reason(value, *, required=True):
    cleaned = value.strip()
    if len(cleaned) > 2000 or (required and not cleaned):
        raise ScheduleValidationError("사유는 공백을 제외해 1~2,000자로 입력하세요.")
    return cleaned


def _validate(project, data):
    reason = _reason(data.reason)
    if data.base_version != project.schedule_version:
        raise ScheduleConflictError("다른 사용자가 일정을 변경했습니다. 최신 일정을 확인하세요.")
    if any(
        value is not None and type(value) is not date for value in schedule_values(data).values()
    ):
        raise ScheduleValidationError("날짜를 올바르게 선택하세요.")
    if schedule_values(data) == schedule_values(project):
        raise ScheduleValidationError("변경된 일정이 없습니다.")
    return reason


def _audit(session, actor, project, action, details):
    record_audit(
        session,
        action=action,
        entity_type="project",
        entity_id=project.id,
        actor_name=actor.display_name,
        details={"actor_id": actor.id, **details},
    )


def _close(entry, actor, status, comment):
    entry.status = status
    entry.reviewed_by_id = actor.id
    entry.reviewed_by_name = actor.display_name
    entry.reviewed_at = datetime.now(UTC).replace(tzinfo=None)
    entry.review_comment = comment


def submit_schedule_request(
    session: Session, *, actor: SessionUser, project_id: int, data: ScheduleInput
) -> ScheduleChangeRequest:
    with commit_or_rollback(session):
        user = require_current_user(session, actor)
        if user.is_admin or user.permission_level == 2:
            raise ScheduleValidationError("2단계 사용자·관리자는 일정 저장을 사용하세요.")
        project = _project(session, project_id)
        reason = _validate(project, data)
        if _pending(session, project.id):
            raise ScheduleConflictError("이미 승인 대기 요청이 있습니다. 기존 요청을 확인하세요.")
        entry = ScheduleChangeRequest(
            project_id=project.id,
            requested_by_id=user.id,
            requested_by_name=user.display_name,
            base_version=project.schedule_version,
            reason=reason,
            status="pending",
            **{f"old_{key}": value for key, value in schedule_values(project).items()},
            **{f"proposed_{key}": value for key, value in schedule_values(data).items()},
        )
        session.add(entry)
        session.flush()
        _audit(
            session,
            actor,
            project,
            "schedule.requested",
            {
                "request_id": entry.id,
                "before": _snapshot(project),
                "after": _snapshot(data),
                "version": project.schedule_version,
                "reason": reason,
            },
        )
    return entry


def update_schedule(
    session: Session, *, actor: SessionUser, project_id: int, data: ScheduleInput
) -> Project:
    with commit_or_rollback(session):
        require_current_user(session, actor, schedule_editor=True)
        project = _project(session, project_id)
        reason = _validate(project, data)
        before = _snapshot(project)
        pending = _pending(session, project.id)
        if pending:
            _close(
                pending, actor, "conflicted", "일정이 직접 수정되었습니다. 새 요청을 제출하세요."
            )
            _audit(session, actor, project, "schedule.conflicted", {"request_id": pending.id})
        for key, value in schedule_values(data).items():
            setattr(project, key, value)
        project.schedule_version += 1
        _audit(
            session,
            actor,
            project,
            "schedule.updated",
            {
                "before": before,
                "after": _snapshot(project),
                "reason": reason,
                "version": project.schedule_version,
                "request_id": None,
            },
        )
    return project


def review_schedule_request(
    session: Session, *, actor: SessionUser, request_id: int, approve: bool, comment: str = ""
) -> ScheduleChangeRequest:
    with commit_or_rollback(session):
        require_current_user(session, actor, schedule_editor=True)
        project_id = session.scalar(
            select(ScheduleChangeRequest.project_id).where(ScheduleChangeRequest.id == request_id)
        )
        if project_id is None:
            raise HTTPException(404, "일정 요청을 찾을 수 없습니다.")
        project = _project(session, project_id)
        entry = session.scalar(
            select(ScheduleChangeRequest)
            .where(ScheduleChangeRequest.id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if entry.status != "pending":
            raise ScheduleConflictError("이미 처리된 요청입니다. 최신 결과를 확인하세요.")
        cleaned = _reason(comment, required=not approve)
        before = _snapshot(project)
        if approve and project.schedule_version != entry.base_version:
            _close(
                entry,
                actor,
                "conflicted",
                "일정이 변경되어 승인할 수 없습니다. 새 요청을 제출하세요.",
            )
        elif approve:
            for field in DATE_FIELDS:
                setattr(project, field, getattr(entry, f"proposed_{field}"))
            project.schedule_version += 1
            _close(entry, actor, "approved", cleaned)
        else:
            _close(entry, actor, "rejected", cleaned)
        _audit(
            session,
            actor,
            project,
            f"schedule.{entry.status}",
            {
                "request_id": entry.id,
                "before": before,
                "after": _snapshot(project),
                "version": project.schedule_version,
                "reason": entry.reason,
                "comment": entry.review_comment,
            },
        )
    return entry
