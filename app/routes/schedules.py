"""일정 조회·변경 요청·승인 화면."""

from datetime import UTC, date, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.audit import AuditLog
from app.models.project import Project
from app.models.schedules import ScheduleChangeRequest
from app.services.schedules import (
    DATE_FIELDS,
    STATUS_LABELS,
    ScheduleConflictError,
    ScheduleInput,
    ScheduleValidationError,
    review_schedule_request,
    schedule_values,
    submit_schedule_request,
    update_schedule,
)

router = APIRouter(tags=["schedules"])
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["kst"] = lambda value: (
    value.replace(tzinfo=UTC).astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    if value
    else "-"
)
LABELS = dict(zip(DATE_FIELDS, ("고객 납기일", "입고 일정", "FOB 일정"), strict=True))


def _project(session, project_id):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다.")
    return project


def _can_edit(user):
    return user.is_admin or user.permission_level == 2


def _render_edit(request, session, project, *, values=None, error=None, message=None, focus=""):
    history = list(
        session.scalars(
            select(AuditLog)
            .where(
                AuditLog.entity_type == "project",
                AuditLog.entity_id == str(project.id),
                AuditLog.action.like("schedule.%"),
            )
            .order_by(AuditLog.id.desc())
            .limit(30)
        )
    )
    pending = session.scalar(
        select(ScheduleChangeRequest).where(
            ScheduleChangeRequest.project_id == project.id,
            ScheduleChangeRequest.status == "pending",
        )
    )
    return templates.TemplateResponse(
        request,
        "schedules/edit.html",
        {
            "project": project,
            "values": values
            if values is not None
            else {
                **schedule_values(project),
                "base_version": project.schedule_version,
                "reason": "",
            },
            "error": error,
            "message": message,
            "pending": pending,
            "history": history,
            "can_edit": _can_edit(request.state.current_user),
            "labels": LABELS,
            "focus": {
                "customer": "target_delivery_date",
                "incoming": "incoming_date",
                "fob": "fob_date",
            }.get(focus, ""),
        },
        status_code=422 if error else 200,
    )


@router.get("/projects/{project_id}/schedule")
def schedule_form(
    request: Request,
    project_id: int,
    focus: str = "",
    saved: bool = False,
    submitted: bool = False,
    session: Session = Depends(get_session),
):
    message = (
        "일정을 저장했습니다."
        if saved
        else "일정 변경을 요청했습니다. 승인 대기 중입니다."
        if submitted
        else None
    )
    return _render_edit(
        request, session, _project(session, project_id), focus=focus, message=message
    )


@router.post("/projects/{project_id}/schedule")
def save_schedule(
    request: Request,
    project_id: int,
    target_delivery_date: str = Form(""),
    incoming_date: str = Form(""),
    fob_date: str = Form(""),
    base_version: int = Form(),
    reason: str = Form(""),
    session: Session = Depends(get_session),
):
    values = {
        "target_delivery_date": target_delivery_date,
        "incoming_date": incoming_date,
        "fob_date": fob_date,
        "base_version": base_version,
        "reason": reason,
    }
    project = _project(session, project_id)
    try:
        dates = {}
        for field in DATE_FIELDS:
            try:
                dates[field] = date.fromisoformat(values[field]) if values[field] else None
            except ValueError as error:
                raise ScheduleValidationError(
                    f"{LABELS[field]} 날짜를 올바르게 선택하세요."
                ) from error
        data = ScheduleInput(**dates, base_version=base_version, reason=reason)
        direct = _can_edit(request.state.current_user)
        operation = update_schedule if direct else submit_schedule_request
        operation(session, actor=request.state.current_user, project_id=project_id, data=data)
    except (ScheduleValidationError, ScheduleConflictError) as error:
        session.rollback()
        session.refresh(project)
        return _render_edit(request, session, project, values=values, error=str(error))
    return RedirectResponse(
        f"/projects/{project_id}/schedule?{'saved' if direct else 'submitted'}=true",
        status_code=303,
    )


@router.get("/schedule-requests")
def schedule_requests(
    request: Request,
    status: Literal["pending", "approved", "rejected", "conflicted", "all"] = "pending",
    page: int = Query(1, ge=1),
    session: Session = Depends(get_session),
):
    user = request.state.current_user
    query = select(ScheduleChangeRequest, Project).join(Project)
    if not _can_edit(user):
        query = query.where(ScheduleChangeRequest.requested_by_id == user.id)
    if status != "all":
        query = query.where(ScheduleChangeRequest.status == status)
    rows = session.execute(
        query.order_by(ScheduleChangeRequest.id.desc()).offset((page - 1) * 30).limit(31)
    ).all()
    return templates.TemplateResponse(
        request,
        "schedules/requests.html",
        {
            "rows": rows[:30],
            "has_next": len(rows) > 30,
            "page": page,
            "selected": status,
            "status_labels": STATUS_LABELS,
            "can_edit": _can_edit(user),
        },
    )


def _entry_for_user(request, session, request_id):
    entry = session.get(ScheduleChangeRequest, request_id)
    if not entry:
        raise HTTPException(404, "일정 요청을 찾을 수 없습니다.")
    user = request.state.current_user
    if not _can_edit(user) and entry.requested_by_id != user.id:
        raise HTTPException(403, "본인이 신청한 요청만 확인할 수 있습니다.")
    return entry


def _render_request(request, session, entry, error=None):
    return templates.TemplateResponse(
        request,
        "schedules/request_detail.html",
        {
            "entry": entry,
            "project": _project(session, entry.project_id),
            "labels": LABELS,
            "status_labels": STATUS_LABELS,
            "can_edit": _can_edit(request.state.current_user),
            "error": error,
        },
        status_code=422 if error else 200,
    )


@router.get("/schedule-requests/{request_id}")
def request_detail(request: Request, request_id: int, session: Session = Depends(get_session)):
    return _render_request(request, session, _entry_for_user(request, session, request_id))


def _review(request, session, request_id, approve, comment):
    entry = _entry_for_user(request, session, request_id)
    try:
        review_schedule_request(
            session,
            actor=request.state.current_user,
            request_id=request_id,
            approve=approve,
            comment=comment,
        )
    except (ScheduleValidationError, ScheduleConflictError) as error:
        return _render_request(request, session, entry, error=str(error))
    return RedirectResponse(f"/schedule-requests/{request_id}", status_code=303)


@router.post("/schedule-requests/{request_id}/approve")
def approve(
    request: Request,
    request_id: int,
    comment: str = Form(""),
    session: Session = Depends(get_session),
):
    return _review(request, session, request_id, True, comment)


@router.post("/schedule-requests/{request_id}/reject")
def reject(
    request: Request,
    request_id: int,
    comment: str = Form(""),
    session: Session = Depends(get_session),
):
    return _review(request, session, request_id, False, comment)
