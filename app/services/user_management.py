"""관리자 계정 관리와 감사 이력의 원자적 저장."""

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AccountRequest, AuthUser
from app.security import SessionUser, require_current_user
from app.services.audit import record_audit
from app.services.auth import create_user, hash_password
from app.services.transactions import commit_or_rollback


def _target(session: Session, user_id: int) -> AuthUser:
    user = session.scalar(
        select(AuthUser)
        .where(AuthUser.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not user:
        raise ValueError("사용자 계정을 찾을 수 없습니다.")
    if user.is_admin:
        raise ValueError("관리자 계정은 이 기능으로 변경할 수 없습니다.")
    return user


def _audit(session, actor, user, action, details=None):
    record_audit(
        session,
        action=action,
        entity_type="auth_user",
        entity_id=user.id,
        actor_name=actor.display_name,
        details={"actor_id": actor.id, **(details or {})},
    )


def set_user_level(
    session: Session, *, actor: SessionUser, user_id: int, permission_level: int
) -> AuthUser:
    with commit_or_rollback(session):
        require_current_user(session, actor, admin=True)
        if permission_level not in (1, 2):
            raise ValueError("권한은 1단계 또는 2단계로 선택하세요.")
        user = _target(session, user_id)
        if user.permission_level != permission_level:
            before = user.permission_level
            user.permission_level = permission_level
            user.auth_version += 1
            _audit(
                session,
                actor,
                user,
                "user.permission_changed",
                {"before": before, "after": permission_level},
            )
    return user


def set_user_active(
    session: Session, *, actor: SessionUser, user_id: int, active: bool
) -> AuthUser:
    with commit_or_rollback(session):
        require_current_user(session, actor, admin=True)
        user = _target(session, user_id)
        if user.is_active != active:
            before = user.is_active
            user.is_active = active
            user.auth_version += 1
            _audit(session, actor, user, "user.active_changed", {"before": before, "after": active})
    return user


def reset_user_password(session: Session, *, actor: SessionUser, user_id: int) -> str:
    with commit_or_rollback(session):
        require_current_user(session, actor, admin=True)
        user = _target(session, user_id)
        password = secrets.token_urlsafe(18)
        user.password_hash = hash_password(password)
        user.must_change_password = True
        user.auth_version += 1
        user.failed_login_count = 0
        user.locked_until = None
        _audit(session, actor, user, "user.password_reset")
    return password


def approve_account(
    session: Session,
    *,
    actor: SessionUser,
    request_id: int,
    temporary_password: str,
    permission_level: int,
) -> AuthUser:
    with commit_or_rollback(session):
        require_current_user(session, actor, admin=True)
        pending = session.scalar(
            select(AccountRequest)
            .where(AccountRequest.id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not pending or pending.status != "pending":
            raise ValueError("대기 중인 신청을 찾을 수 없습니다.")
        user = create_user(
            session,
            email=pending.email,
            display_name=pending.display_name,
            temporary_password=temporary_password,
            permission_level=permission_level,
        )
        pending.status = "approved"
        pending.reviewed_at = datetime.now(UTC).replace(tzinfo=None)
        _audit(
            session,
            actor,
            user,
            "user.account_approved",
            {"request_id": pending.id, "permission_level": permission_level},
        )
    return user


def reject_account(session: Session, *, actor: SessionUser, request_id: int) -> AccountRequest:
    with commit_or_rollback(session):
        require_current_user(session, actor, admin=True)
        pending = session.scalar(
            select(AccountRequest)
            .where(AccountRequest.id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not pending or pending.status != "pending":
            raise ValueError("대기 중인 신청을 찾을 수 없습니다.")
        pending.status = "rejected"
        pending.reviewed_at = datetime.now(UTC).replace(tzinfo=None)
        record_audit(
            session,
            action="user.account_rejected",
            entity_type="account_request",
            entity_id=pending.id,
            actor_name=actor.display_name,
            details={"actor_id": actor.id},
        )
    return pending
