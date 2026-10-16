"""비밀번호 검증, 로그인 잠금과 사용자 생성 규칙."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuthUser

PASSWORD_ITERATIONS = 600_000
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str) -> str:
    """계정 식별에 사용할 이메일을 정규화한다."""

    email = value.strip().casefold()
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("올바른 이메일 주소를 입력하세요.")
    return email


def validate_password(value: str) -> None:
    """계정 비밀번호 최소 길이를 확인한다."""

    if len(value) < 12 or len(value) > 256:
        raise ValueError("비밀번호는 12자 이상 256자 이하여야 합니다.")


def hash_password(password: str) -> str:
    """PBKDF2-SHA256와 사용자별 임의 salt로 비밀번호를 저장한다."""

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)

    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${encode(salt)}${encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    """저장된 비밀번호 해시를 상수 시간 비교로 검증한다."""

    try:
        algorithm, iteration_text, salt_text, digest_text = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False

        def decode(value: str) -> bytes:
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

        iterations = int(iteration_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        expected = decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), decode(salt_text), iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_user(
    session: Session,
    *,
    email: str,
    display_name: str,
    temporary_password: str,
    is_admin: bool = False,
    permission_level: int = 1,
) -> AuthUser:
    """새 계정을 생성하고 첫 로그인에서 비밀번호를 바꾸도록 표시한다."""

    if permission_level not in (1, 2):
        raise ValueError("권한은 1단계 또는 2단계로 선택하세요.")
    normalized_email = normalize_email(email)
    validate_password(temporary_password)
    name = display_name.strip()
    if not name or len(name) > 120:
        raise ValueError("이름은 1자 이상 120자 이하여야 합니다.")
    if session.scalar(select(AuthUser.id).where(AuthUser.email == normalized_email)):
        raise ValueError("이미 등록된 이메일입니다.")
    user = AuthUser(
        email=normalized_email,
        display_name=name,
        password_hash=hash_password(temporary_password),
        is_admin=is_admin,
        permission_level=2 if is_admin else permission_level,
        is_active=True,
        must_change_password=True,
    )
    session.add(user)
    session.flush()
    return user


def login_locked(user: AuthUser, *, now: datetime | None = None) -> bool:
    """계정의 임시 로그인 잠금 상태를 반환한다."""

    return bool(user.locked_until and user.locked_until > (now or datetime.now()))


def record_failed_login(user: AuthUser, *, now: datetime | None = None) -> None:
    """연속 로그인 실패 횟수를 누적하고 8회부터 15분 잠근다."""

    current = now or datetime.now()
    user.failed_login_count += 1
    if user.failed_login_count >= 8:
        user.locked_until = current + timedelta(minutes=15)
