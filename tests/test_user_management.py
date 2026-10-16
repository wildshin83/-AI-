"""관리자 권한·활성 상태·비밀번호 재발급 규칙."""

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.auth import AccountRequest
from app.security import SessionUser
from app.services.auth import verify_password
from app.services.user_management import (
    approve_account,
    reset_user_password,
    set_user_active,
    set_user_level,
)


def identity(user):
    return SessionUser(
        user.id,
        user.display_name,
        user.is_admin,
        user.must_change_password,
        user.permission_level,
        user.auth_version,
    )


def test_level_changes_only_target_and_noop_keeps_session(account_db, accounts):
    member, reviewer, admin = accounts
    set_user_level(account_db, actor=identity(admin), user_id=member.id, permission_level=2)
    assert (member.permission_level, member.auth_version, reviewer.auth_version) == (2, 2, 1)
    set_user_level(account_db, actor=identity(admin), user_id=member.id, permission_level=2)
    assert member.auth_version == 2


def test_state_change_preserves_level_and_noop(account_db, accounts):
    member, _, admin = accounts
    set_user_active(account_db, actor=identity(admin), user_id=member.id, active=False)
    assert not member.is_active and member.permission_level == 1
    assert member.auth_version == 2
    set_user_active(account_db, actor=identity(admin), user_id=member.id, active=False)
    assert member.auth_version == 2
    set_user_active(account_db, actor=identity(admin), user_id=member.id, active=True)
    assert member.auth_version == 3


def test_reset_keeps_inactive_clears_lock_and_never_audits_password(account_db, accounts):
    member, _, admin = accounts
    member.is_active = False
    member.failed_login_count = 8
    member.locked_until = datetime(2099, 1, 1)
    account_db.commit()
    password = reset_user_password(account_db, actor=identity(admin), user_id=member.id)
    assert len(password) >= 20 and verify_password(password, member.password_hash)
    assert member.must_change_password and not member.is_active and member.auth_version == 2
    assert member.failed_login_count == 0 and member.locked_until is None
    assert password not in str(list(account_db.scalars(select(AuditLog.details))))


def test_only_admin_can_change_general_accounts(account_db, accounts):
    member, reviewer, admin = accounts
    with pytest.raises(HTTPException) as error:
        set_user_level(account_db, actor=identity(reviewer), user_id=member.id, permission_level=2)
    assert error.value.status_code == 403
    account_db.rollback()
    with pytest.raises(ValueError):
        set_user_active(account_db, actor=identity(admin), user_id=admin.id, active=False)
    account_db.rollback()
    with pytest.raises(ValueError):
        set_user_level(account_db, actor=identity(admin), user_id=member.id, permission_level=3)


def test_account_approval_assigns_level_once(account_db, accounts):
    pending = AccountRequest(email="new@example.test", display_name="new", message="test")
    account_db.add(pending)
    account_db.commit()
    user = approve_account(
        account_db,
        actor=identity(accounts[2]),
        request_id=pending.id,
        temporary_password="Test-new-password-123",
        permission_level=2,
    )
    assert user.permission_level == 2 and pending.status == "approved"
    with pytest.raises(ValueError):
        approve_account(
            account_db,
            actor=identity(accounts[2]),
            request_id=pending.id,
            temporary_password="Test-new-password-123",
            permission_level=2,
        )


def test_rejection_is_audited_and_blocks_later_approval(account_db, accounts):
    from app.services.user_management import reject_account

    pending = AccountRequest(email="rejected@example.test", display_name="new", message="test")
    account_db.add(pending)
    account_db.commit()
    reject_account(account_db, actor=identity(accounts[2]), request_id=pending.id)
    assert pending.status == "rejected"
    assert account_db.scalar(select(AuditLog).where(AuditLog.action == "user.account_rejected"))
    with pytest.raises(ValueError):
        approve_account(
            account_db,
            actor=identity(accounts[2]),
            request_id=pending.id,
            temporary_password="Example-password-123",
            permission_level=1,
        )


def test_admin_forms_and_reset_response(account_db, accounts, sign_in):
    member, _, admin = accounts
    client = sign_in(admin)
    response = client.get("/admin/users?search=member")
    assert f"/admin/users/{member.id}/permission" in response.text
    assert f"/admin/users/{member.id}/status" in response.text
    response = client.post(f"/admin/users/{member.id}/reset-password")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "임시 비밀번호" in response.text
    assert "발급한 임시 비밀번호" not in client.get("/admin/users").text


def test_permission_downgrade_invalidates_old_identity(account_db, accounts):
    from app.security import require_current_user

    old_identity = identity(accounts[1])
    set_user_level(
        account_db, actor=identity(accounts[2]), user_id=accounts[1].id, permission_level=1
    )
    with pytest.raises(HTTPException) as error:
        require_current_user(account_db, old_identity, schedule_editor=True)
    assert error.value.status_code == 401
