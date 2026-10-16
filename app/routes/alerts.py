"""경고 목록, 재계산, 조치 상태 변경 화면."""

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.alerts import Alert, AlertAction
from app.models.bom import BomItem
from app.models.project import Project
from app.services.alerts import refresh_project_alerts, update_alert_status

router = APIRouter(tags=["alerts"])
templates = Jinja2Templates(directory="app/templates")


def _project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    return project


@router.get("/projects/{project_id}/alerts")
def project_alerts(request: Request, project_id: int, session: Session = Depends(get_session)):
    project = _project_or_404(session, project_id)
    alerts = list(
        session.scalars(
            select(Alert)
            .where(Alert.project_id == project.id)
            .order_by(Alert.status.asc(), Alert.severity.desc(), Alert.updated_at.desc())
        )
    )
    item_names = {
        item.id: item.drawing_number
        for item in session.scalars(
            select(BomItem).where(BomItem.id.in_([entry.bom_item_id for entry in alerts]))
        )
    }
    actions = {
        entry.id: list(
            session.scalars(
                select(AlertAction)
                .where(AlertAction.alert_id == entry.id)
                .order_by(AlertAction.created_at.desc())
            )
        )
        for entry in alerts
    }
    return templates.TemplateResponse(
        request,
        "alerts/list.html",
        {
            "project": project,
            "alerts": alerts,
            "item_names": item_names,
            "actions": actions,
            "error": None,
        },
    )


@router.post("/projects/{project_id}/alerts/refresh")
def refresh_alerts(project_id: int, session: Session = Depends(get_session)):
    _project_or_404(session, project_id)
    refresh_project_alerts(session, project_id=project_id)
    return RedirectResponse(
        url=f"/projects/{project_id}/alerts", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/alerts/{alert_id}/status")
def alert_status(
    request: Request,
    alert_id: int,
    status_value: str = Form(),
    actor_name: str = Form(),
    action_note: str = Form(),
    alternative_reviewed: bool = Form(False),
    expected_resolution_date: date | None = Form(None),
    session: Session = Depends(get_session),
):
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="경고를 찾을 수 없습니다.")
    try:
        update_alert_status(
            session,
            alert=alert,
            status=status_value,
            actor_name=actor_name,
            action_note=action_note,
            alternative_reviewed=alternative_reviewed,
            expected_resolution_date=expected_resolution_date,
        )
    except ValueError as error:
        project = _project_or_404(session, alert.project_id)
        alerts = list(
            session.scalars(select(Alert).where(Alert.project_id == project.id).order_by(Alert.id))
        )
        return templates.TemplateResponse(
            request,
            "alerts/list.html",
            {
                "project": project,
                "alerts": alerts,
                "item_names": {},
                "actions": {},
                "error": str(error),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return RedirectResponse(
        url=f"/projects/{alert.project_id}/alerts", status_code=status.HTTP_303_SEE_OTHER
    )
