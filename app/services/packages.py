# ruff: noqa: E501
"""안전한 프로젝트 패키지·백업 메타데이터 생성."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bom import BomItem, BomRevision
from app.models.imports import UploadBatch
from app.models.packages import ExchangePackage
from app.models.project import Project
from app.models.quotes import QuoteAdjustment, QuoteItem, QuoteVersion
from app.services.audit import record_audit
from app.storage.packages import create_json_package, read_package_manifest


def export_project_package(
    session: Session, *, project: Project, created_by: str
) -> ExchangePackage:
    if not created_by.strip():
        raise ValueError("패키지 생성자는 필수입니다.")
    revisions = list(session.scalars(select(BomRevision).where(BomRevision.project_id == project.id)))
    revision_items = {
        revision.id: list(
            session.scalars(select(BomItem).where(BomItem.bom_revision_id == revision.id))
        )
        for revision in revisions
    }
    quotes = list(session.scalars(select(QuoteVersion).where(QuoteVersion.project_id == project.id)))
    payload = {
        "format_version": 2,
        "exported_at": datetime.now().isoformat(),
        "project": _project_payload(project),
        "bom_revisions": [_revision_payload(entry, revision_items[entry.id]) for entry in revisions],
        "quote_versions": [_quote_payload(session, entry, revisions) for entry in quotes],
        "notice": "가져오기 전 차이 확인이 필요하며 기존 데이터를 자동 덮어쓰지 않습니다.",
    }
    path = create_json_package(file_stem=f"{project.project_number}_package", payload=payload)
    package = ExchangePackage(
        project_id=project.id,
        package_type="project",
        stored_path=str(path),
        created_by=created_by.strip(),
    )
    session.add(package)
    session.flush()
    record_audit(
        session,
        action="project_package.exported",
        entity_type="exchange_package",
        entity_id=package.id,
        actor_name=created_by.strip(),
    )
    session.commit()
    return package


def _project_payload(project: Project) -> dict[str, object]:
    return {
        "number": project.project_number,
        "name": project.project_name,
        "customer_name": project.customer_name,
        "equipment_unit": project.equipment_unit,
        "manager_name": project.manager_name,
        "status": project.status,
        "incoming_date": project.incoming_date.isoformat() if project.incoming_date else None,
        "fob_date": project.fob_date.isoformat() if project.fob_date else None,
        "target_delivery_date": project.target_delivery_date.isoformat()
        if project.target_delivery_date
        else None,
    }


def _revision_payload(revision: BomRevision, items: list[BomItem]) -> dict[str, object]:
    return {
        "revision_name": revision.revision_name,
        "memo": revision.memo,
        "items": [
            {
                "source_item_number": item.source_item_number,
                "drawing_number": item.drawing_number,
                "normalized_drawing_number": item.normalized_drawing_number,
                "title": item.title,
                "component": item.component,
                "material": item.material,
                "treatment": item.treatment,
                "specification": item.specification,
                "maker": item.maker,
                "quantity": str(item.quantity),
                "item_type": item.item_type,
                "source_data": item.source_data,
            }
            for item in items
        ],
    }


def _quote_payload(
    session: Session, quote: QuoteVersion, revisions: list[BomRevision]
) -> dict[str, object]:
    revision_name = next(
        (revision.revision_name for revision in revisions if revision.id == quote.bom_revision_id), None
    )
    return {
        "version_number": quote.version_number,
        "bom_revision_name": revision_name,
        "status": quote.status,
        "submission_date": quote.submission_date.isoformat() if quote.submission_date else None,
        "submission_note": quote.submission_note,
        "created_by": quote.created_by,
        "items": [_quote_item_payload(item) for item in session.scalars(select(QuoteItem).where(QuoteItem.quote_version_id == quote.id))],
        "adjustments": [
            {"name": entry.name, "amount": str(entry.amount), "memo": entry.memo}
            for entry in session.scalars(select(QuoteAdjustment).where(QuoteAdjustment.quote_version_id == quote.id))
        ],
    }


def _quote_item_payload(item: QuoteItem) -> dict[str, object]:
    return {
        "drawing_number": item.drawing_number,
        "item_name": item.item_name,
        "item_type": item.item_type,
        "material": item.material,
        "treatment": item.treatment,
        "specification": item.specification,
        "maker": item.maker,
        "quantity": str(item.quantity),
        "material_cost": str(item.material_cost),
        "machining_cost": str(item.machining_cost),
        "treatment_cost": str(item.treatment_cost),
        "purchased_unit_price": str(item.purchased_unit_price),
        "memo": item.memo,
    }


def import_project_package(session: Session, *, package_path: Path, imported_by: str) -> Project:
    """충돌 없는 프로젝트 패키지만 새 프로젝트로 가져온다. 기존 데이터는 덮어쓰지 않는다."""

    manifest = read_package_manifest(package_path)
    if manifest.get("format_version") != 2:
        raise ValueError("가져올 수 없는 프로젝트 패키지 형식입니다.")
    incoming = manifest.get("project")
    if not isinstance(incoming, dict):
        raise ValueError("프로젝트 정보가 없는 패키지입니다.")
    number = str(incoming.get("number") or "").strip()
    if not number or session.scalar(select(Project).where(Project.project_number == number)):
        raise ValueError("동일 프로젝트 번호가 있어 자동 병합·덮어쓰기를 허용하지 않습니다.")
    project = Project(
        project_number=number,
        project_name=str(incoming.get("name") or ""),
        customer_name=str(incoming.get("customer_name") or ""),
        equipment_unit=str(incoming.get("equipment_unit") or ""),
        manager_name=str(incoming.get("manager_name") or imported_by).strip(),
        status=str(incoming.get("status") or "견적"),
        target_delivery_date=_optional_date(incoming.get("target_delivery_date")),
        incoming_date=_optional_date(incoming.get("incoming_date")),
        fob_date=_optional_date(incoming.get("fob_date")),
    )
    session.add(project)
    session.flush()
    revisions: dict[str, BomRevision] = {}
    for raw_revision in manifest.get("bom_revisions", []):
        if not isinstance(raw_revision, dict):
            continue
        revision = _import_revision(session, project, raw_revision)
        revisions[revision.revision_name] = revision
    for raw_quote in manifest.get("quote_versions", []):
        if isinstance(raw_quote, dict):
            _import_quote(session, project, revisions, raw_quote)
    record_audit(
        session,
        action="project_package.imported",
        entity_type="project",
        entity_id=project.id,
        actor_name=imported_by.strip() or None,
        details={"project_number": project.project_number},
    )
    session.commit()
    session.refresh(project)
    return project


def _optional_date(value: object) -> date | None:
    return date.fromisoformat(value) if isinstance(value, str) and value else None


def _import_revision(session: Session, project: Project, raw: dict[str, object]) -> BomRevision:
    upload = UploadBatch(
        project_id=project.id,
        source_type="package_import",
        status="confirmed",
        original_file_name="project_package.json",
        stored_path="package://manifest.json",
        mapping={},
        issues=[],
    )
    session.add(upload)
    session.flush()
    revision = BomRevision(
        project_id=project.id,
        upload_batch_id=upload.id,
        revision_name=str(raw.get("revision_name") or ""),
        memo=raw.get("memo") if isinstance(raw.get("memo"), str) else None,
    )
    session.add(revision)
    session.flush()
    for raw_item in raw.get("items", []):
        if not isinstance(raw_item, dict):
            continue
        session.add(
            BomItem(
                bom_revision_id=revision.id,
                source_item_number=raw_item.get("source_item_number"),
                drawing_number=str(raw_item.get("drawing_number") or ""),
                normalized_drawing_number=str(raw_item.get("normalized_drawing_number") or ""),
                title=raw_item.get("title"), component=raw_item.get("component"),
                material=raw_item.get("material"), treatment=raw_item.get("treatment"),
                specification=raw_item.get("specification"), maker=raw_item.get("maker"),
                quantity=Decimal(str(raw_item.get("quantity") or "0")),
                item_type=raw_item.get("item_type"),
                source_data=raw_item.get("source_data") if isinstance(raw_item.get("source_data"), dict) else {},
            )
        )
    return revision


def _import_quote(
    session: Session, project: Project, revisions: dict[str, BomRevision], raw: dict[str, object]
) -> None:
    revision = revisions.get(str(raw.get("bom_revision_name") or ""))
    if revision is None:
        return
    quote = QuoteVersion(
        project_id=project.id, bom_revision_id=revision.id,
        version_number=int(raw.get("version_number") or 0), status=str(raw.get("status") or "draft"),
        submission_date=datetime.fromisoformat(raw["submission_date"]) if raw.get("submission_date") else None,
        submission_note=raw.get("submission_note"), created_by=str(raw.get("created_by") or project.manager_name),
    )
    session.add(quote)
    session.flush()
    for item in raw.get("items", []):
        if isinstance(item, dict):
            session.add(QuoteItem(quote_version_id=quote.id, **_quote_item_kwargs(item)))
    for adjustment in raw.get("adjustments", []):
        if isinstance(adjustment, dict):
            session.add(QuoteAdjustment(quote_version_id=quote.id, name=str(adjustment.get("name") or ""), amount=Decimal(str(adjustment.get("amount") or "0")), memo=adjustment.get("memo")))


def _quote_item_kwargs(item: dict[str, object]) -> dict[str, object]:
    numeric_keys = {"quantity", "material_cost", "machining_cost", "treatment_cost", "purchased_unit_price"}
    fields = {
        "item_name", "item_type", "material", "treatment", "specification", "maker", "memo"
    }
    values = {key: item.get(key) for key in fields}
    values["drawing_number"] = str(item.get("drawing_number") or "")
    for key in numeric_keys:
        values[key] = Decimal(str(item.get(key) or "0"))
    return values


def compare_project_package(session: Session, *, package_path: Path) -> dict[str, object]:
    """가져오기 전 패키지와 현 로컬 프로젝트의 충돌 여부만 확인한다."""

    manifest = read_package_manifest(package_path)
    incoming = manifest.get("project", {})
    project_number = incoming.get("number") if isinstance(incoming, dict) else None
    local = session.scalar(select(Project).where(Project.project_number == project_number))
    return {
        "incoming_project": incoming,
        "local_exists": local is not None,
        "automatic_overwrite": False,
        "action_required": "병합 또는 별도 신규 등록을 사용자가 선택해야 합니다.",
    }
