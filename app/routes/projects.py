"""프로젝트 목록·등록·아카이브 화면 라우트."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.alerts import Alert
from app.models.project import Project, ProjectStatus
from app.services.cs_contacts import CS_MANAGER_NAMES
from app.services.project_codes import (
    CUSTOMER_CODES,
    CUSTOMER_OPTIONS,
    DEPARTMENT_CODES,
    EQUIPMENT_CODES,
    LINE_CODES,
    MAIN_PROJECT_CODES,
    ORDER_CODES,
    PROJECT_TYPES,
    SITE_CODES,
    UNIT_CODES,
    YEARS,
    ProjectCodeError,
    suggest_project_number,
)
from app.services.projects import (
    ProjectCreateInput,
    ProjectNumberAlreadyExistsError,
    create_project,
    set_project_archived,
)

router = APIRouter(tags=["projects"])
templates = Jinja2Templates(directory="app/templates")


def _project_form_context(project=None, error=None):
    return {
        "project": project,
        "statuses": list(ProjectStatus),
        "customer_options": CUSTOMER_OPTIONS,
        "customer_codes": CUSTOMER_CODES,
        "project_types": PROJECT_TYPES,
        "site_codes": SITE_CODES,
        "equipment_codes": EQUIPMENT_CODES,
        "years": YEARS,
        "line_codes": LINE_CODES,
        "unit_codes": UNIT_CODES,
        "department_codes": DEPARTMENT_CODES,
        "main_project_codes": MAIN_PROJECT_CODES,
        "order_codes": ORDER_CODES,
        "cs_manager_names": CS_MANAGER_NAMES,
        "error": error,
    }


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
        _project_form_context(),
    )


@router.get("/projects/code-preview")
def project_code_preview(
    project_type: str = Query(""),
    customer_name: str = Query(""),
    site_code: str = Query(""),
    equipment_code: str = Query(""),
    award_year: str = Query(""),
    line_code: str = Query(""),
    unit_code: str = Query(""),
    department_code: str = Query(""),
    main_project_code: str = Query(""),
    order_code: str = Query(""),
    order_serial: str = Query(""),
    session: Session = Depends(get_session),
):
    selection = {
        "project_type": project_type,
        "customer_name": customer_name,
        "site_code": site_code,
        "equipment_code": equipment_code,
        "award_year": award_year,
        "line_code": line_code,
        "unit_code": unit_code,
        "department_code": department_code,
        "main_project_code": main_project_code,
        "order_code": order_code,
        "order_serial": order_serial,
    }
    try:
        number = suggest_project_number(session, selection)
        return JSONResponse(
            {
                "project_number": number,
                "order_serial": number[-3:] if order_code else "",
            }
        )
    except ProjectCodeError as error:
        return JSONResponse({"error": str(error)}, status_code=422)


@router.post("/projects")
def project_create(
    request: Request,
    project_type: str = Form(),
    site_code: str = Form(),
    equipment_code: str = Form(),
    award_year: str = Form(),
    line_code: str = Form(),
    unit_code: str = Form(),
    department_code: str = Form(),
    main_project_code: str = Form(),
    order_code: str = Form(""),
    order_serial: str = Form(""),
    project_name: str = Form(),
    customer_name: str = Form(),
    equipment_unit: str = Form(),
    manager_name: str = Form(),
    project_status: str = Form(ProjectStatus.QUOTATION.value),
    target_delivery_date: date | None = Form(None),
    incoming_date: date | None = Form(None),
    fob_date: date | None = Form(None),
    session: Session = Depends(get_session),
):
    selection = {
        "project_type": project_type,
        "customer_name": customer_name,
        "site_code": site_code,
        "equipment_code": equipment_code,
        "award_year": award_year,
        "line_code": line_code,
        "unit_code": unit_code,
        "department_code": department_code,
        "main_project_code": main_project_code,
        "order_code": order_code,
        "order_serial": order_serial,
    }
    try:
        if manager_name not in CS_MANAGER_NAMES:
            raise ValueError("담당자는 CS사업부 인원 중에서 선택하세요.")
        project_number = suggest_project_number(session, selection)
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
                incoming_date=incoming_date,
                fob_date=fob_date,
            ),
        )
    except (ValueError, ProjectNumberAlreadyExistsError) as error:
        project = {
            **selection,
            "project_number": None,
            "project_name": project_name,
            "customer_name": customer_name,
            "equipment_unit": equipment_unit,
            "manager_name": manager_name,
            "status": project_status,
            "target_delivery_date": target_delivery_date,
            "incoming_date": incoming_date,
            "fob_date": fob_date,
        }
        return templates.TemplateResponse(
            request,
            "projects/form.html",
            _project_form_context(project, str(error)),
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
        request,
        "projects/detail.html",
        {
            "project": project,
            "unread_count": unread_count or 0,
            "statuses": list(ProjectStatus),
            "active_status_index": next(
                (index for index, item in enumerate(ProjectStatus) if item.value == project.status),
                0,
            ),
        },
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
