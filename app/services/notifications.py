"""메일 알림의 선택적 SMTP 전송."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send_account_request_notification(
    *, admin_email: str | None, applicant_email: str, applicant_name: str, request_id: int
) -> bool:
    """SMTP 설정이 있을 때 신청 알림을 보내고, 미설정/전송 오류는 False로 반환한다."""

    host = os.getenv("BOM_SMTP_HOST", "").strip()
    sender = os.getenv("BOM_SMTP_FROM", "").strip()
    if not (admin_email and host and sender):
        return False
    try:
        port = int(os.getenv("BOM_SMTP_PORT", "587"))
        message = EmailMessage()
        message["Subject"] = f"BOM 서비스 계정 승인 요청: {applicant_name}"
        message["From"] = sender
        message["To"] = admin_email
        message.set_content(
            f"신규 계정 승인 요청이 접수되었습니다.\n\n"
            f"신청자: {applicant_name}\n이메일: {applicant_email}\n"
            f"요청 번호: {request_id}\n\n"
            "관리자 화면의 사용자 계정 관리에서 내용을 확인하고 승인 또는 반려해 주세요."
        )
        with smtplib.SMTP(host, port, timeout=10) as client:
            if os.getenv("BOM_SMTP_STARTTLS", "true").strip().casefold() in {"1", "true", "yes"}:
                client.starttls()
            username = os.getenv("BOM_SMTP_USERNAME", "").strip()
            password = os.getenv("BOM_SMTP_PASSWORD", "")
            if username:
                client.login(username, password)
            client.send_message(message)
        return True
    except (OSError, ValueError, smtplib.SMTPException):
        return False
