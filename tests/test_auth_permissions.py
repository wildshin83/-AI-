"""캐시·계정 변경과 관계없는 최신 인증 상태 검증."""

from datetime import datetime

import pytest

from tests.conftest import TEST_PASSWORD


def test_deactivated_cookie_rejected_after_previous_request(account_db, accounts, sign_in):
    member = accounts[0]
    client = sign_in(member)
    assert client.get("/projects").status_code == 200
    member.is_active = False
    member.auth_version += 1
    account_db.commit()
    response = client.get("/projects", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?notice=expired"
    assert 'bom_session=""' in response.headers["set-cookie"]


def test_old_version_rejected_after_reactivation(account_db, accounts, sign_in):
    client = sign_in(accounts[0])
    accounts[0].auth_version += 2
    account_db.commit()
    assert client.get("/projects", follow_redirects=False).status_code == 303


@pytest.mark.parametrize("locked", [False, True])
def test_inactive_login_correct_password_shows_expired(account_db, accounts, web_client, locked):
    accounts[0].is_active = False
    accounts[0].locked_until = datetime(2099, 1, 1) if locked else None
    account_db.commit()
    response = web_client.post(
        "/login", data={"email": accounts[0].email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 403
    assert "권한이 만료되어 접속할 수 없습니다." in response.text
    response = web_client.post("/login", data={"email": accounts[0].email, "password": "incorrect"})
    assert response.status_code == 401
    assert "권한이 만료" not in response.text


def test_first_login_requires_password_change(account_db, accounts, sign_in):
    accounts[0].must_change_password = True
    account_db.commit()
    response = sign_in(accounts[0]).get("/projects", follow_redirects=False)
    assert response.headers["location"] == "/account/password"


def test_origin_and_admin_gate(accounts, sign_in):
    client = sign_in(accounts[0])
    assert client.get("/admin/users").status_code == 403
    assert client.post("/logout", headers={"origin": "https://untrusted.test"}).status_code == 403


def test_business_responses_are_not_browser_cached(accounts, sign_in):
    response = sign_in(accounts[0]).get("/projects")
    assert response.headers.get("cache-control") == "no-store"


def test_password_change_rechecks_reset_session(account_db, accounts, sign_in, monkeypatch):
    import app.security as security
    from tests.test_user_management import identity

    member = accounts[0]
    stale = identity(member)
    client = sign_in(member)
    member.auth_version += 1
    account_db.commit()
    monkeypatch.setattr(security, "_verified_user", lambda token: stale)
    response = client.post(
        "/account/password",
        data={"current_password": TEST_PASSWORD, "new_password": "Other-new-password-123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?notice=expired"


def test_login_never_upgrades_verified_password_to_new_reset_version(
    account_db, accounts, web_client, monkeypatch
):
    from app.security import _session_identity

    real_commit = account_db.commit
    member = accounts[0]

    def reset_after_commit():
        real_commit()
        member.auth_version += 1
        member.must_change_password = True
        real_commit()

    monkeypatch.setattr(account_db, "commit", reset_after_commit)
    response = web_client.post(
        "/login", data={"email": member.email, "password": TEST_PASSWORD}, follow_redirects=False
    )
    assert response.status_code == 303
    assert _session_identity(response.cookies["bom_session"]) == (member.id, 1)
