"""로그인, 첫 관리자 설정, 비밀번호 변경 화면."""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.auth import AuthUser
from app.security import clear_session_cookie, set_session_cookie
from app.services.auth import (
    create_user,
    hash_password,
    login_locked,
    record_failed_login,
    validate_password,
    verify_password,
)

router = APIRouter(tags=["authentication"])
templates = Jinja2Templates(directory="app/templates")


def _safe_next(value: str) -> str:
    return value if value.startswith("/") and not value.startswith("//") else "/projects"


@router.get("/login")
def login_form(request: Request, next: str = "/projects"):
    if request.state.current_user:
        target = (
            "/account/password" if request.state.current_user.must_change_password else "/projects"
        )
        return RedirectResponse(target, status_code=303)
    return templates.TemplateResponse(
        request, "auth/login.html", {"error": None, "next": _safe_next(next)}
    )


@router.post("/login")
def login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
    next: str = Form("/projects"),
    session: Session = Depends(get_session),
):
    user = session.scalar(select(AuthUser).where(AuthUser.email == email.strip().casefold()))
    valid = user is not None and user.is_active and not login_locked(user)
    if not valid or not verify_password(password, user.password_hash if user else ""):
        if user and user.is_active and not login_locked(user):
            record_failed_login(user)
            session.commit()
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "이메일 또는 비밀번호를 확인하세요.", "next": _safe_next(next)},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user.failed_login_count = 0
    user.locked_until = None
    session.commit()
    response = RedirectResponse(
        "/account/password" if user.must_change_password else _safe_next(next),
        status_code=303,
    )
    set_session_cookie(response, user)
    return response


@router.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=303)
    clear_session_cookie(response)
    return response


@router.get("/setup-admin")
def setup_admin_form(request: Request, session: Session = Depends(get_session)):
    configured = len(os.getenv("BOM_ADMIN_SETUP_KEY", "").encode()) >= 32
    admin_exists = bool(session.scalar(select(AuthUser.id).where(AuthUser.is_admin.is_(True))))
    if not configured or admin_exists:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "auth/setup_admin.html", {"error": None})


@router.post("/setup-admin")
def setup_admin(
    request: Request,
    setup_key: str = Form(),
    email: str = Form(),
    display_name: str = Form(),
    password: str = Form(),
    session: Session = Depends(get_session),
):
    expected_key = os.getenv("BOM_ADMIN_SETUP_KEY", "")
    if len(expected_key.encode()) < 32:
        return RedirectResponse("/login", status_code=303)
    if not hmac.compare_digest(setup_key.encode(), expected_key.encode()):
        return templates.TemplateResponse(
            request,
            "auth/setup_admin.html",
            {"error": "설정 키가 올바르지 않습니다."},
            status_code=403,
        )

    if session.scalar(select(AuthUser.id).where(AuthUser.is_admin.is_(True))):
        return RedirectResponse("/login", status_code=303)
    try:
        if session.bind and session.bind.dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(7241951301)"))
        if session.scalar(select(AuthUser.id).where(AuthUser.is_admin.is_(True))):
            return RedirectResponse("/login", status_code=303)
        user = create_user(
            session,
            email=email,
            display_name=display_name,
            temporary_password=password,
            is_admin=True,
        )
        user.must_change_password = False
        session.commit()
    except ValueError as error:
        session.rollback()
        return templates.TemplateResponse(
            request,
            "auth/setup_admin.html",
            {"error": str(error)},
            status_code=422,
        )
    except IntegrityError:
        session.rollback()
        return templates.TemplateResponse(
            request,
            "auth/setup_admin.html",
            {"error": "관리자 계정을 만들지 못했습니다. 이메일이 이미 등록됐는지 확인하세요."},
            status_code=409,
        )

    response = RedirectResponse("/projects", status_code=303)
    set_session_cookie(response, user)
    return response


@router.get("/account/password")
def password_form(request: Request):
    return templates.TemplateResponse(request, "auth/password.html", {"error": None})


@router.post("/account/password")
def change_password(
    request: Request,
    new_password: str = Form(),
    current_password: str = Form(""),
    session: Session = Depends(get_session),
):
    current_user: AuthUser = request.state.current_user
    user = session.get(AuthUser, current_user.id)
    if not user.must_change_password and not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "auth/password.html",
            {"error": "현재 비밀번호를 확인하세요."},
            status_code=422,
        )
    try:
        validate_password(new_password)
    except ValueError as error:
        return templates.TemplateResponse(
            request, "auth/password.html", {"error": str(error)}, status_code=422
        )
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.auth_version += 1
    session.commit()
    response = RedirectResponse("/projects", status_code=303)
    set_session_cookie(response, user)
    return response
