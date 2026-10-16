"""서명 쿠키 기반 로그인 세션과 앱 전체 권한 검사."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from urllib.parse import quote, urlsplit

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.db import SessionLocal
from app.models.auth import AuthUser

COOKIE_NAME = "bom_session"
SESSION_MAX_AGE = 12 * 60 * 60
_development_secret = secrets.token_bytes(32)


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

        public_path = path in {"/login", "/setup-admin", "/health"} or path.startswith("/static/")
        user = None
        if path != "/health" and not path.startswith("/static/"):
            identity = _session_identity(request.cookies.get(COOKIE_NAME, ""))
            if identity:
                with SessionLocal() as session:
                    candidate = session.scalar(select(AuthUser).where(AuthUser.id == identity[0]))
                    if (
                        candidate is not None
                        and candidate.is_active
                        and candidate.auth_version == identity[1]
                    ):
                        user = candidate
                        session.expunge(user)

        request.state.current_user = user
        if not public_path:
            if user is None:
                if path.startswith("/admin"):
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
        return response
