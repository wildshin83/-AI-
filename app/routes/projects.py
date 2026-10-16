"""프로젝트 목록·등록·아카이브 화면 라우트."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.alerts import Alert
from app.models.project import Project, ProjectStatus
from app.services.projects import (
    ProjectCreateInput,
    ProjectNumberAlreadyExistsError,
    create_project,
    set_project_archived,
)

router = APIRouter(tags=["projects"])
templates = Jinja2Templates(directory="app/templates")


def _project_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    return project


@router.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse(url="/projects", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/projects")
def project_list(
    request: Request,
    search: str | None = None,
    include_archived: bool = False,
    session: Session = Depends(get_session),
):
    unread_statuses = ("unread", "acknowledged", "in_progress")
    query = (
        select(Project, func.count(Alert.id))
        .outerjoin(
            Alert,
            (Alert.project_id == Project.id) & Alert.status.in_(unread_statuses),
        )
        .group_by(Project.id)
    )
    if not include_archived:
        query = query.where(Project.is_archived.is_(False))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            Project.project_number.ilike(term)
            | Project.project_name.ilike(term)
            | Project.customer_name.ilike(term)
            | Project.equipment_unit.ilike(term)
            | Project.manager_name.ilike(term)
        )
    query = query.order_by(
        Project.is_archived,
        Project.target_delivery_date,
        Project.created_at.desc(),
    )
    rows = session.execute(query).all()
    projects = [project for project, _ in rows]
    unread_counts = {project.id: count for project, count in rows if count}
    return templates.TemplateResponse(
        request,
        "projects/list.html",
        {
            "projects": projects,
            "search": search or "",
            "include_archived": include_archived,
            "statuses": list(ProjectStatus),
            "unread_counts": unread_counts,
        },
    )


@router.get("/projects/new")
def project_new_form(request: Request):
    return templates.TemplateResponse(
        request,
        "projects/form.html",
        {"project": None, "statuses": list(ProjectStatus), "error": None},
    )


@router.post("/projects")
def project_create(
    request: Request,
    project_number: str = Form(),
    project_name: str = Form(),
    customer_name: str = Form(),
    equipment_unit: str = Form(),
    manager_name: str = Form(),
    project_status: str = Form(ProjectStatus.QUOTATION.value),
    target_delivery_date: date | None = Form(None),
    session: Session = Depends(get_session),
):
    try:
        project = create_project(
            session,
            ProjectCreateInput(
                project_number=project_number,
                project_name=project_name,
                customer_name=customer_name,
                equipment_unit=equipment_unit,
                manager_name=manager_name,
                status=project_status,
                target_delivery_date=target_delivery_date,
            ),
        )
    except (ValueError, ProjectNumberAlreadyExistsError) as error:
        return templates.TemplateResponse(
            request,
            "projects/form.html",
            {
                "project": {
                    "project_number": project_number,
                    "project_name": project_name,
                    "customer_name": customer_name,
                    "equipment_unit": equipment_unit,
                    "manager_name": manager_name,
                    "status": project_status,
                    "target_delivery_date": target_delivery_date,
                },
                "statuses": list(ProjectStatus),
                "error": str(error),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return RedirectResponse(
        url=f"/projects/{project.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/projects/{project_id}")
def project_detail(request: Request, project_id: int, session: Session = Depends(get_session)):
    project = _project_or_404(session, project_id)
    unread_count = session.scalar(
        select(func.count(Alert.id)).where(
            Alert.project_id == project.id,
            Alert.status.in_(["unread", "acknowledged", "in_progress"]),
        )
    )
    return templates.TemplateResponse(
        request, "projects/detail.html", {"project": project, "unread_count": unread_count or 0}
    )


@router.post("/projects/{project_id}/archive")
def project_archive(project_id: int, session: Session = Depends(get_session)) -> RedirectResponse:
    project = _project_or_404(session, project_id)
    set_project_archived(session, project, archived=True)
    return RedirectResponse(url="/projects", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/projects/{project_id}/restore")
def project_restore(project_id: int, session: Session = Depends(get_session)) -> RedirectResponse:
    project = _project_or_404(session, project_id)
    set_project_archived(session, project, archived=False)
    return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)
