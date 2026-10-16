# Project Schedules and User Permissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task when native execution is selected. Steps use checkbox (`- [ ]`) syntax for tracking. Subagent execution is available only if explicitly selected by the user.

**Goal:** 세 일정의 조회·수정·승인과 계정 단계·활성 상태·분실 대응을 기존 인증 서비스에 구현한다.

**Architecture:** 기존 계정 서비스·관리자 화면을 확장하고 일정 승인 모델·서비스·라우트를 분리한다. 계정 상태와 세션 버전을 DB에서 확인하고 일정 버전·행 잠금으로 중복 승인과 오래된 변경을 막는다. 기존 감사 서비스와 v2 패키지를 재사용한다.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, SQLAlchemy 2, Alembic, PostgreSQL/psycopg, SQLite 개발 DB, pytest, Ruff. 신규 제품 의존성은 필요하지 않다.

**Spec:** `docs/superpowers/specs/2026-10-16-project-schedules-and-user-permissions-design.md` (2026-10-16 사용자 승인)

## Global Constraints

- 기존 고객 납기일 필드 `target_delivery_date`와 관리자 `is_admin`을 유지한다.
- 사용자 단계는 정수 1 또는 2, 기존 일반 계정·Excel 등록 기본값은 1이다.
- 신규 날짜 `incoming_date`, `fob_date`는 nullable Date, `schedule_version`은 기본 1이다.
- 신청·직접 수정·반려 사유는 공백 제거 후 1~2,000자, 승인 의견은 선택 입력 2,000자 이하다.
- 한 프로젝트에 pending 요청 하나, 상태는 pending/approved/rejected/conflicted다.
- 비활성 안내 문구는 정확히 `권한이 만료되어 접속할 수 없습니다.` 이다.
- 임시 비밀번호는 서버 난수 20자 이상, 해시 저장, 발급 시 한 번 표시, 응답 `Cache-Control: no-store` 적용.
- 관리자 계정의 단계 변경·비활성화·재발급은 일반 사용자 행 기능으로 제공하지 않는다.
- 활성 여부·세션 버전은 보호된 요청마다 DB에서 확인한다. 민감 쓰기는 서비스에서 최신 권한을 확인한다.
- 요청 출처 검증·첫 로그인 비밀번호 변경·공유 프로젝트 범위를 유지한다. 자동 이메일을 추가하지 않는다.
- `.env`, 참고자료, `.local-data/`, 기존 무관한 변경은 커밋하지 않는다. 제품 작업 완료 시 필요한 파일만 커밋·푸시한다.
- 검증 데이터는 격리된 로컬 임시 DB 또는 별도 PostgreSQL 테스트 스키마에 넣고 업무 DB에는 테스트 계정을 만들지 않는다.

## Review Focus

1. 비활성화 직전 발급된 쿠키가 다른 인스턴스에서 재사용되는 경우: 캐시와 관계없이 거절. Task 2 테스트에 포함.
2. 권한/상태 저장에서 값이 같거나 다른 행의 ID가 전달되는 경우: 대상만 갱신, 무변경 시 세션 유지. Task 3 테스트에 포함.
3. 잠김·비활성 계정의 재발급: 로그인 잠금만 초기화하고 비활성 상태 유지. Task 3 테스트에 포함.
4. 날짜가 변경된 뒤 원래 값으로 복귀한 경우: 같은 날짜여도 이전 버전 요청은 충돌. Task 4 테스트에 포함.
5. 날짜를 지우거나 구형 v2 패키지에 신규 날짜가 없는 경우: NULL로 보존하고 기존 고객 날짜 유지. Tasks 4·6 테스트에 포함.

## File Structure

- `app/models/auth.py`, `app/models/project.py`, 신규 `app/models/schedules.py`, `app/models/__init__.py`: 계정 단계·날짜·버전·요청 ORM.
- 신규 `migrations/versions/20261016_0012_schedule_permissions.py`: 추가 스키마와 기존 데이터 기본값.
- `app/security.py`, `app/services/auth.py`, `app/routes/auth.py`: 최신 인증·권한, 계정 생성 단계와 만료 안내.
- 신규 `app/services/user_management.py`: 관리자 단계·활성 상태 저장·재발급·가입 승인 트랜잭션.
- `app/routes/admin.py`, `app/templates/admin/users.html`: 기존 화면에 행별 폼·검색·권한 선택. 기존 중복 렌더링은 공통 함수 사용.
- 신규 `app/services/schedules.py`, `app/routes/schedules.py`, `app/templates/schedules/{edit,requests,request_detail}.html`: 일정 변경과 승인 UI/업무 규칙.
- `app/main.py`, `app/templates/base.html`: 라우트 등록과 요청함 링크.
- `app/services/projects.py`, `app/routes/projects.py`, `app/templates/projects/{form,detail,list}.html`, `app/static/app.css`: 세 날짜 입력·반응형 표시.
- `app/services/packages.py`: v2 날짜 왕복.
- 신규 `tests/{conftest,test_user_management,test_auth_permissions,test_schedules,test_schedule_routes,test_schedule_migration,test_schedules_postgresql}.py`, 기존 `tests/{test_projects,test_packages}.py`: 격리된 의미 있는 회귀 검증.

## Task 1: 데이터 모델·마이그레이션

**Files:** 위 ORM 4개, 신규 migration, `tests/test_schedule_migration.py`.

**Interfaces:** `AuthUser.permission_level: int`; `Project.incoming_date/fob_date: date | None`; `Project.schedule_version: int`; `ScheduleChangeRequest`는 승인 설계 6절의 필드를 제공한다. 기존·제안 날짜는 각각 `old_*`/`proposed_*` 접두어, 고객 날짜는 `*_target_delivery_date`로 명명한다. `requested_by_id/name`, `reviewed_by_id/name`, `base_version`, `reason`, `status`, `created_at`, `reviewed_at`, `review_comment`를 사용한다.

- [ ] 기존 리비전 0011에 일반·관리자 계정과 고객 날짜를 넣은 임시 SQLite 파일을 준비하는 마이그레이션 테스트 작성. head 이후 기존 날짜 동일, 일반 단계 1, 관리자 단계 2, 버전 1, 신규 날짜 NULL을 단언한다. 현재 head에서 신규 필드 부재로 실패하는지 확인한다.
- [ ] 0012와 ORM 구현. 단계·상태·양수 버전 CHECK, 프로젝트/계정 FK, 프로젝트·상태와 신청자 조회 인덱스 추가. 관리자 단계 기본값 보정. SQLite 제약 추가는 batch 방식 사용.
- [ ] `python -m pytest tests/test_schedule_migration.py -q` 실행. 격리된 DB에서 upgrade 및 빈 신규 테이블 downgrade/upgrade 확인. 모든 테스트 PASS 후 대상 파일 커밋.

## Task 2: 인증 컨텍스트와 실시간 세션 무효화

**Files:** `app/security.py`, `app/services/auth.py`, `app/routes/auth.py`, `tests/conftest.py`, `tests/test_auth_permissions.py`.

**Interfaces:** `SessionUser`에 `permission_level`, `auth_version` 추가. `require_current_user(session: Session, identity: SessionUser, *, admin: bool = False, schedule_editor: bool = False) -> AuthUser`를 security에 제공한다. 최신 활성·버전 일치 및 요청한 권한을 검사하고 위반 시 HTTP 401/403. `create_user(..., permission_level: int = 1)`은 1·2 외 값 거절, 관리자면 2로 정규화.

- [ ] 임시 DB와 `get_session`, `security.SessionLocal` 교체 fixture 작성. 실제 해시·서명 쿠키로 로그인·권한 변경·비활성화를 검증하며 외부 DB 접속이 없게 한다.
- [ ] `test_deactivated_cookie_rejected_across_cache_instances`, `test_old_version_rejected_after_reactivation`, `test_inactive_login_correct_password_shows_expired`, `test_inactive_wrong_password_generic`, `test_current_role_required_for_sensitive_write` 작성. 만료 문구와 쿠키 제거·리다이렉트, 1단계 검토자 거절을 단언하고 실패 확인.
- [ ] 캐시를 신뢰하는 인증 흐름을 매 보호 요청의 최신 DB 조회로 교체. 비활성/구버전 이유를 구분하고 고정 `/login?notice=expired`로 안내. 로그인 POST는 비밀번호 검증 후 활성 여부 확인, 기존 실패 횟수·잠금·첫 로그인 흐름 유지. DB 오류 시 보호 화면을 제공하지 않는다.
- [ ] `python -m pytest tests/test_auth_permissions.py -q` 실행, 인증·출처 검증과 첫 로그인 변경 시나리오 PASS 후 커밋.

## Task 3: 관리자 사용자 제어와 계정 복구

**Files:** 신규 `app/services/user_management.py`, 기존 admin route/template, 신규 `tests/test_user_management.py`.

**Interfaces:** `set_user_level(session, *, actor: SessionUser, user_id: int, permission_level: int) -> AuthUser`; `set_user_active(session, *, actor: SessionUser, user_id: int, active: bool) -> AuthUser`; `reset_user_password(session, *, actor: SessionUser, user_id: int) -> str`; `approve_account(session, *, actor: SessionUser, request_id: int, temporary_password: str, permission_level: int) -> AuthUser`. 각 서비스가 최신 관리자 검사·대상 잠금·감사·commit/rollback 담당.

- [ ] 테스트 작성 후 실패 확인: 다른 행 보존, 동일 값 저장 시 `auth_version` 유지, 1·2단계 선택 승인, 중복 승인 1회 처리, 관리자 대상 작업 거절, 일반 사용자 위조 요청 403, 재발급 후 잠금 해제·비활성 유지·새 해시 검증·평문 감사 미포함.
- [ ] 서비스 구현. 단계/상태 실제 변경 시만 버전 증가. 재발급은 `secrets.token_urlsafe(18)`와 기존 해시 사용, 첫 로그인 변경 강제, 실패 횟수/잠금 초기화.
- [ ] `POST /admin/users/{user_id}/permission`, `/status`, `/reset-password` 추가. 권한·상태 각각 별도 행별 폼/저장 버튼, 가입 승인·직접 등록에 단계 select 추가. `GET /admin/users?search=` 이름·이메일 검색, 모든 관리 응답에서 신청 목록·오류·검색 조건 공통 렌더링. Excel 형식·기본 1단계 유지.
- [ ] 재발급 폼에 대상 계정과 기존 세션 종료 영향 표시. 제출 응답에 임시 비밀번호 한 번 표시하고 no-store 적용, GET/새로고침 결과에는 재노출하지 않는다. HTTP 재전송은 재조회가 아닌 새 발급으로 처리.
- [ ] `python -m pytest tests/test_user_management.py tests/test_auth_permissions.py -q` 실행. 재발급 HTTP 응답 헤더와 다음 로그인 변경 강제, 행별 UI·서버 권한 검증 PASS 후 커밋.

## Task 4: 일정 변경·승인 서비스

**Files:** 신규 `app/services/schedules.py`, `tests/test_schedules.py`.

**Interfaces:** immutable `ScheduleInput(target_delivery_date: date | None, incoming_date: date | None, fob_date: date | None, base_version: int, reason: str)`; `submit_schedule_request(session, *, actor: SessionUser, project_id: int, data: ScheduleInput) -> ScheduleChangeRequest`; `update_schedule(session, *, actor: SessionUser, project_id: int, data: ScheduleInput) -> Project`; `review_schedule_request(session, *, actor: SessionUser, request_id: int, approve: bool, comment: str = '') -> ScheduleChangeRequest`. 서비스가 commit/rollback을 담당한다. 입력 검증·오래된 편집 제출 오류는 `ScheduleValidationError(ValueError)` / `ScheduleConflictError(ValueError)`, 권한 위반은 Task 2의 예외를 사용한다. 요청 자체를 conflicted로 마감한 검토 결과는 예외 대신 처리된 모델로 반환한다.

- [ ] テスト 작성 후 실패 확인: 1단계 제출은 원본 불변/pending 생성, 2단계·관리자 승인/직접 변경, 사유 공백·2,001자 거절, NULL 날짜 변경, 변경 없는 제출 거절, 2번째 pending 거절, 이미 처리된 요청 재승인 차단, 반려 일정 보존, 과거→변경→과거 복귀 후 이전 요청 충돌.
- [ ] 서비스 구현. 공통 날짜·사유 검증과 최신 사용자 확인 후 프로젝트→요청 순서로 행 잠금. 버전 확인·세 날짜 수정·버전 증가·감사·처리 결과는 원자적 저장. 직접 변경 시 기존 pending을 conflicted 처리. 충돌 요청 마감은 commit 후 반환하고 HTTP는 안내 메시지로 처리해 rollback으로 마감이 취소되지 않게 한다.
- [ ] `python -m pytest tests/test_schedules.py -q` 실행. 변경·감사 중 오류를 주입했을 때 부분 적용이 없는 롤백 테스트까지 PASS 후 커밋.

## Task 5: 일정 편집·승인 화면과 요청함

**Files:** 신규 schedules route/templates, 기존 main/base, `tests/test_schedule_routes.py`.

**Interfaces:** `GET/POST /projects/{project_id}/schedule` (폼 필드는 세 날짜, `base_version`, `reason`); `GET /schedule-requests?status=pending&page=1`; `GET /schedule-requests/{request_id}`; `POST /schedule-requests/{request_id}/approve` 및 `/reject` (`comment`). POST 일정 라우트는 최신 권한에 따라 Task 4의 제출/직접 수정 서비스를 선택.

- [ ] 라우트 테스트 작성 후 실패 확인: 1단계는 본인 요청만 조회, 다른 신청 요청 상세 403, 2단계는 전체 조회/검토 가능, 페이지당 30건·유효한 status·page≥1 검증, 출처 불일치 POST 403, 날짜 오류 입력값 보존, 처리 중복·충돌 안내.
- [ ] 라우트·템플릿 구현. 날짜 입력은 달력, `focus=customer|incoming|fob` 허용 목록으로 초점 선택. 변경 이력과 대기 요청 표시, 요청자 승인 요청 버튼/검토자 일정 저장 버튼, 반려 사유 필수. 감사 이력은 해당 프로젝트·일정 action으로만 조회.
- [ ] 메뉴에 일정 요청함 추가. 좁은 화면에서는 메뉴 영역에 가로 스크롤을 허용해 링크가 겹치지 않게 한다. 일정/계정 문구를 자동 escape하고 이력 시각은 Asia/Seoul로 표시한다.
- [ ] `python -m pytest tests/test_schedule_routes.py tests/test_schedules.py -q` 실행. 권한별 응답·입력값 보존·게시된 날짜 반영 확인 후 커밋.

## Task 6: 프로젝트와 패키지 날짜 연결

**Files:** 기존 projects 서비스·route·3개 template·CSS, packages 서비스, `tests/test_projects.py`, `tests/test_packages.py`.

**Interfaces:** `ProjectCreateInput` 끝에 `incoming_date: date | None = None`, `fob_date: date | None = None` 추가해 기존 호출 호환. 패키지 `project.incoming_date/fob_date`는 ISO 문자열 또는 null, format_version=2 유지.

- [ ] 서비스/패키지 테스트 작성 후 실패 확인: 최초 세 날짜 저장, 구형 v2의 고객 날짜 보존·신규 날짜 NULL, 신규 v2 왕복, 신규 프로젝트 버전 1, 기존 번호 중복 import 차단.
- [ ] 등록 폼·서버 입력/오류 재표시에 두 날짜 추가, 목표 납기일 레이블을 고객 납기일로 변경. 상세 요약에 세 날짜 링크, 일정 영역 안 균등 열, 단계 표시는 진행 상태 바로 아래 유지. 모바일 순서는 진행 상태/단계→일정→보관 상태. 기존 납기 정렬을 유지.
- [ ] 패키지 내보내기/가져오기에 두 선택 날짜 필드 연결. 승인 요청·권한·버전을 포함하지 않는다.
- [ ] `python -m pytest tests/test_projects.py tests/test_packages.py tests/test_schedule_routes.py -q` 실행. 데스크탑 1280px, 모바일 390px·320px에서 화면을 열어 날짜·단계·메뉴·행별 저장 버튼의 겹침/가로 넘침을 확인하고 커밋.

## Task 7: PostgreSQL 동시성·문서·운영 반영

**Files:** 신규 `tests/test_schedules_postgresql.py`; `prd.md`, `BOM_관리서비스_기능요구사항_및_설계안.md`, `VERCEL_DEMO_DEPLOYMENT.md`, `SUPABASE_DATABASE_SETUP.md`, `TEST_SCENARIOS.md`, `change log.md`; 오류 발견 시 `error.md`.

- [ ] 별도 테스트 PostgreSQL에만 연결하는 `BOM_TEST_POSTGRES_URL` fixture 작성. 임의 이름의 임시 스키마를 생성·정리하고 런타임·마이그레이션 DB URL로 대체 실행하지 않는다. 동시 제출 두 세션은 pending 1개, 동시 승인 두 세션은 버전 1회 증가, 승인과 직접 수정 충돌에서 마지막 확정 상태 보존을 단언한다. 테스트 URL 없으면 명시적으로 skip해 미검증임을 기록한다.
- [ ] `python -m pytest tests/test_schedules_postgresql.py -q` 실행. 실제 PostgreSQL PASS 또는 외부 미검증 상태를 보고한다. SQLite PASS를 동시성 검증으로 대신하지 않는다.
- [ ] `python -m pytest tests/test_schedule_migration.py tests/test_auth_permissions.py tests/test_user_management.py tests/test_schedules.py tests/test_schedule_routes.py tests/test_projects.py tests/test_packages.py -q`, `python -m ruff check app tests`, `python -m compileall -q app` 실행. 기존 관련 실패가 있으면 원인 확인 후 해결하고 재실행. 테스트는 제품 DB가 아닌 fixture DB만 사용한다.
- [ ] 문서에 단계별 일정 권한, 계정 비활성화/재활성화, 재발급 전달 절차, 기존 일반 계정 기본 단계 1, 기존 세션 재로그인을 기록. PRD/요구사항의 승인·세부 권한 제외 항목에 이번 승인된 고도화 예외를 반영한다. 변경 이력에는 실제 검증 결과만 기재한다.
- [ ] 실제 DB 백업 유무·접속 대상·마이그레이션 권한을 비밀정보 없이 확인. 기존 승인 범위의 DB에 `python -m alembic upgrade head`, `python -m alembic current` 적용·확인. 권한/접속 제약 시 임의의 다른 DB로 변경하지 말고 제약을 보고한다. 새 테이블의 런타임 역할 권한도 확인한다.
- [ ] 필요한 파일만 명시적으로 stage하고 `git diff --cached --check` 및 staged diff로 비밀정보·무관 변경 제외 확인. 커밋·`git push origin main` 후 Vercel 실제 배포 상태가 Ready인지 확인. `health`와 비로그인 보호 경로·로그인 화면은 읽기 요청으로 확인하고, 실제 계정 비밀번호/상태를 검증 목적으로 변경하지 않는다.
- [ ] 배포 URL·커밋·실행된 검증·미검증 항목을 보고한다. 원격 배포 미확인/미적용은 완료로 표현하지 않는다.

## 실행 결과 (2026-10-16)

사용자가 Native 실행을 승인해 직접 구현했다. Tasks 1~6 및 Task 7의 코드·문서·로컬 검증과 Supabase 마이그레이션을 완료했다. 린트·컴파일 통과, 원본 참고자료 검사 제외 63건 통과, 별도 PostgreSQL URL 미제공으로 3건 skip. 전체 테스트에서는 기존 고객 견적 원본 양식 부재 검사 1건이 실패했다. 최종 리뷰의 로그인/재발급 경합 및 가입 승인/반려 경합을 수정하고 회귀 검증했다. 기능 구현 커밋을 포함한 `4b61c2d`의 Vercel Production Ready를 확인했다. 운영 사이트에서 세 날짜, 사용자별 제어, 일정 요청함 GET을 확인했다. 공식 Production 주소의 health는 PostgreSQL ok이며 쿠키 없는 업무 접근은 로그인으로 차단된다. 이후 비활성+로그인 잠금 동시 상태 안내를 보완했으며 후속 배포를 확인한다.

후속 사용자 요청에 따라 비밀번호 재발급 이메일을 추가했다. 제공된 회사 SMTP는 TLS 미지원이므로 실제 발송은 암호화 SMTP 설정 후 확인해야 한다. 관리자 가입 신청 메일은 중단한다.

## Self-review and Handoff

- 설계 1~13절은 Tasks 1~7에 대응한다. 일정과 계정 관리가 같은 권한·세션 규칙을 사용하므로 하나의 순차 계획으로 유지한다.
- 구현 시 바뀌는 공통 인터페이스는 해당 task의 Interfaces를 먼저 갱신해 호출자와 일치시킨다.
- 이 문서는 실행 전 검토 대상이다. 권장 실행 방식은 이 대화에서 직접 순서대로 구현하는 Native 방식이다. 사용자 실행 방식 선택과 계획 검토 후 구현을 시작한다.
