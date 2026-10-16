"""프로젝트 등록·검색·아카이브의 업무 규칙."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectStatus
from app.services.audit import record_audit


class ProjectNumberAlreadyExistsError(ValueError):
    """동일 프로젝트 번호 등록을 막는다."""


@dataclass(frozen=True)
class ProjectCreateInput:
    project_number: str
    project_name: str
    customer_name: str
    equipment_unit: str
    manager_name: str
    status: str
    target_delivery_date: date | None


def _clean_required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name}은(는) 필수 입력입니다.")
    return cleaned


def create_project(session: Session, data: ProjectCreateInput) -> Project:
    """검증된 프로젝트를 만들고 감사 이력을 같은 트랜잭션에 기록한다."""

    project = Project(
        project_number=_clean_required(data.project_number, "프로젝트 번호"),
        project_name=_clean_required(data.project_name, "프로젝트명"),
        customer_name=_clean_required(data.customer_name, "고객사"),
        equipment_unit=_clean_required(data.equipment_unit, "장비명/호기"),
        manager_name=_clean_required(data.manager_name, "담당자"),
        status=(
            data.status
            if data.status in {item.value for item in ProjectStatus}
            else ProjectStatus.QUOTATION.value
        ),
        target_delivery_date=data.target_delivery_date,
    )
    session.add(project)
    try:
        session.flush()
    except IntegrityError as error:
        raise ProjectNumberAlreadyExistsError("이미 등록된 프로젝트 번호입니다.") from error

    record_audit(
        session,
        action="project.created",
        entity_type="project",
        entity_id=project.id,
        actor_name=project.manager_name,
        details={"project_number": project.project_number, "project_name": project.project_name},
    )
    session.commit()
    session.refresh(project)
    return project


def project_list_query(
    *, include_archived: bool, search: str | None = None
) -> Select[tuple[Project]]:
    """목록과 대시보드에서 재사용하는 프로젝트 검색 쿼리."""

    query = select(Project)
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
    return query.order_by(
        Project.is_archived,
        Project.target_delivery_date,
        Project.created_at.desc(),
    )


def list_projects(
    session: Session, *, include_archived: bool, search: str | None = None
) -> list[Project]:
    """검색 조건에 맞는 프로젝트를 반환한다."""

    query = project_list_query(include_archived=include_archived, search=search)
    return list(session.scalars(query))


def set_project_archived(session: Session, project: Project, *, archived: bool) -> Project:
    """삭제 대신 아카이브 상태를 변경하고 이력을 남긴다."""

    project.is_archived = archived
    record_audit(
        session,
        action="project.archived" if archived else "project.restored",
        entity_type="project",
        entity_id=project.id,
        actor_name=project.manager_name,
        details={"project_number": project.project_number},
    )
    session.commit()
    session.refresh(project)
    return project
