"""SMTP 메일 전송. 오류와 비밀정보를 로그에 남기지 않는다."""

import os
import smtplib
import ssl
from email.message import EmailMessage


def _send(message: EmailMessage) -> bool:
    host = os.getenv("BOM_SMTP_HOST", "").strip()
    sender = os.getenv("BOM_SMTP_FROM", "").strip()
    if not (host and sender and message["To"]):
        return False
    message["From"] = sender
    try:
        port = int(os.getenv("BOM_SMTP_PORT", "587"))
        if port == 465:
            connection = smtplib.SMTP_SSL(
                host, port, timeout=10, context=ssl.create_default_context()
            )
        else:
            connection = smtplib.SMTP(host, port, timeout=10)
        with connection as client:
            if port != 465:
                # 임시 비밀번호를 포함하므로 암호화되지 않은 SMTP는 사용하지 않는다.
                if os.getenv("BOM_SMTP_STARTTLS", "true").strip().casefold() not in {
                    "1",
                    "true",
                    "yes",
                }:
                    return False
                client.starttls(context=ssl.create_default_context())
            username = os.getenv("BOM_SMTP_USERNAME", "").strip()
            if username:
                client.login(username, os.getenv("BOM_SMTP_PASSWORD", ""))
            client.send_message(message)
        return True
    except (OSError, ValueError, smtplib.SMTPException):
        return False


def send_account_request_notification(
    *, admin_email: str | None, applicant_email: str, applicant_name: str, request_id: int
) -> bool:
    if not admin_email:
        return False
    message = EmailMessage()
    message["To"] = admin_email
    message["Subject"] = "BOM 서비스 계정 승인 요청"
    message.set_content(
        f"신청자: {applicant_name}\n이메일: {applicant_email}\n요청 번호: {request_id}\n"
        "관리자 화면에서 확인해 주세요."
    )
    return _send(message)


def send_temporary_password(*, email: str, name: str, password: str) -> bool:
    message = EmailMessage()
    message["To"] = email
    message["Subject"] = "BOM 관리 서비스 임시 비밀번호 발급"
    message.set_content(
        f"{name}님, 관리자가 임시 비밀번호를 발급했습니다.\n\n"
        f"아이디: {email}\n임시 비밀번호: {password}\n\n"
        "기존에 사용하던 BOM 관리 서비스 주소에서 로그인하세요.\n"
        "로그인 후 반드시 새 비밀번호로 변경해야 합니다.\n"
        "본인이 요청하지 않았다면 관리자에게 알려주세요."
    )
    return _send(message)
