"""서명 쿠키 기반 로그인 세션과 앱 전체 권한 검사."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.db import SessionLocal
from app.models.auth import AuthUser

COOKIE_NAME = "bom_session"
SESSION_MAX_AGE = 12 * 60 * 60
_development_secret = secrets.token_bytes(32)


@dataclass(frozen=True, slots=True)
class SessionUser:
    """요청 시 DB에서 확인한 로그인 정보."""

    id: int
    display_name: str
    is_admin: bool
    must_change_password: bool
    permission_level: int
    auth_version: int


def _verified_user(identity: tuple[int, int]) -> SessionUser | None:
    """모든 보호된 요청에서 활성 상태와 세션 버전을 새로 확인한다."""
    with SessionLocal() as session:
        row = session.execute(select(
            AuthUser.id, AuthUser.display_name, AuthUser.is_admin,
            AuthUser.must_change_password, AuthUser.permission_level, AuthUser.auth_version,
        ).where(AuthUser.id == identity[0], AuthUser.auth_version == identity[1],
                AuthUser.is_active.is_(True))).one_or_none()
    return SessionUser(*row) if row else None


def require_current_user(session: Session, identity: SessionUser, *, admin: bool = False,
                         schedule_editor: bool = False) -> AuthUser:
    """민감 쓰기에서 최신 권한을 확인하고 트랜잭션 동안 계정 변경과 직렬화한다."""
    user = session.scalar(select(AuthUser).where(AuthUser.id == identity.id)
                          .with_for_update(read=True).execution_options(populate_existing=True))
    if not user or not user.is_active or user.auth_version != identity.auth_version:
        raise HTTPException(401, "권한이 만료되어 접속할 수 없습니다.")
    if user.must_change_password:
        raise HTTPException(403, "먼저 비밀번호를 변경하세요.")
    if admin and not user.is_admin:
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    if schedule_editor and not (user.is_admin or user.permission_level == 2):
        raise HTTPException(403, "2단계 사용자 또는 관리자 권한이 필요합니다.")
    return user


def _secret() -> bytes:
    configured = os.getenv("BOM_SESSION_SECRET", "")
    if configured:
        if len(configured.encode()) < 32:
            raise RuntimeError("BOM_SESSION_SECRET은 32바이트 이상이어야 합니다.")
        return configured.encode()
    if os.getenv("VERCEL"):
        raise RuntimeError("배포 환경에는 BOM_SESSION_SECRET 설정이 필요합니다.")
    return _development_secret


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_session_token(user: AuthUser) -> str:
    payload = json.dumps(
        {"sub": user.id, "ver": user.auth_version, "exp": int(time.time()) + SESSION_MAX_AGE},
        separators=(",", ":"),
    ).encode()
    encoded = _encode(payload)
    signature = hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_encode(signature)}"


def _session_identity(token: str) -> tuple[int, int] | None:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode(supplied_signature)):
            return None
        payload = json.loads(_decode(encoded))
        if int(payload["exp"]) <= int(time.time()):
            return None
        return int(payload["sub"]), int(payload["ver"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def set_session_cookie(response: Response, user: AuthUser) -> None:
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(user),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=bool(os.getenv("VERCEL")),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME, path="/", httponly=True, secure=bool(os.getenv("VERCEL")), samesite="lax"
    )


def _origin_matches_request(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer")
        if not referer:
            return False
        origin = f"{urlsplit(referer).scheme}://{urlsplit(referer).netloc}"
    return urlsplit(origin).netloc.casefold() == request.headers.get("host", "").casefold()


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """로그인·관리자 권한과 교차 사이트 요청 방지를 모든 라우트에 적용한다."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        path = request.url.path
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not _origin_matches_request(
            request
        ):
            return JSONResponse(
                status_code=403, content={"detail": "요청 출처를 확인할 수 없습니다."}
            )

        public_path = path in {
            "/login", "/setup-admin", "/account-requests", "/account-requests/new", "/health"
        } or path.startswith("/static/")
        user = None
        has_session_cookie = bool(request.cookies.get(COOKIE_NAME))
        needs_user_context = (
            not path.startswith("/static/")
            and path != "/health"
            and (not public_path or has_session_cookie)
        )
        if needs_user_context:
            identity = _session_identity(request.cookies.get(COOKIE_NAME, ""))
            if identity:
                try:
                    user = _verified_user(identity)
                except SQLAlchemyError:
                    return JSONResponse(status_code=503,
                                        content={"detail": "인증 상태를 확인할 수 없습니다."})

        request.state.current_user = user
        if not public_path:
            if user is None:
                if has_session_cookie:
                    response = RedirectResponse("/login?notice=expired", status_code=303)
                elif path.startswith("/admin"):
                    destination = quote(
                        request.url.path + (f"?{request.url.query}" if request.url.query else ""),
                        safe="/",
                    )
                    response = RedirectResponse(f"/login?next={destination}", status_code=303)
                else:
                    response = RedirectResponse("/login", status_code=303)
                if request.cookies.get(COOKIE_NAME):
                    clear_session_cookie(response)
                return response

            if path.startswith("/admin") and not user.is_admin:
                return JSONResponse(
                    status_code=403, content={"detail": "관리자 권한이 필요합니다."}
                )
            if (
                user.must_change_password
                and path not in {"/account/password", "/logout", "/health"}
                and not path.startswith("/static/")
            ):
                return RedirectResponse("/account/password", status_code=303)

        response = await call_next(request)
        if path.startswith("/static/") and response.status_code < 400:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
