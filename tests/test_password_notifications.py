"""실제 메일 없이 수신자·TLS·실패 처리를 검증한다."""

import smtplib

from app.services.notifications import send_temporary_password


def test_temporary_password_goes_only_to_account_email(monkeypatch):
    sent = []

    class SMTP:
        def __init__(self, host, port, timeout):
            assert (host, port) == ("smtp.example.test", 587)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self, **kwargs):
            sent.append("TLS")

        def login(self, username, password):
            assert username == "test-sender"

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setenv("BOM_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("BOM_SMTP_FROM", "sender@example.test")
    monkeypatch.setenv("BOM_SMTP_USERNAME", "test-sender")
    monkeypatch.setattr(smtplib, "SMTP", SMTP)
    assert send_temporary_password(
        email="member@example.test", name="member", password="test-temporary-password"
    )
    assert sent[0] == "TLS"
    assert sent[1]["To"] == "member@example.test"
    assert "test-temporary-password" in sent[1].get_content()


def test_missing_smtp_is_reported_without_exception(monkeypatch):
    monkeypatch.delenv("BOM_SMTP_HOST", raising=False)
    assert not send_temporary_password(
        email="member@example.test", name="member", password="test-temporary-password"
    )


def test_signup_does_not_send_abandoned_admin_notifications(monkeypatch, accounts, web_client):
    def forbidden(*args, **kwargs):
        raise AssertionError("가입 신청 메일은 발송하지 않아야 합니다.")

    monkeypatch.setenv("BOM_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("BOM_SMTP_FROM", "sender@example.test")
    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    response = web_client.post(
        "/account-requests",
        data={"email": "applicant@example.test", "display_name": "가상 신청자", "message": "test"},
    )
    assert response.status_code == 200
