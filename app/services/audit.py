"""감사 이력 기록을 공통 서비스로 제공한다."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record_audit(
    session: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int,
    actor_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """트랜잭션에 포함되는 감사 이력 한 건을 추가한다."""

    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        actor_name=actor_name,
        details=details,
    )
    session.add(entry)
    return entry
