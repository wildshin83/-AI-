# 인증 사용자 대상 Vercel 공개 배포

## 목적과 접근 범위

GitHub `main` 브랜치에서 Vercel로 배포하는 인증형 BOM·ERP·견적 서비스 운영 절차다. 앱은 이메일·비밀번호 로그인을 요구하고, 신규 계정은 관리자가 직접 추가하거나 계정 Excel로 등록한다. 로그인하지 않은 방문자는 업무 화면에 접근할 수 없다.

관리자가 등록한 일반 사용자는 공유된 프로젝트·BOM·ERP·견적 데이터를 모두 볼 수 있다. 프로젝트별 권한과 열람 전용 역할은 아직 지원하지 않으므로, 계정 발급 전 업무상 접근 범위를 확인한다.

## 계정과 보안

- 앱은 `/login`, 최초 관리자 설정(`/setup-admin`), `/health`, 정적 파일을 제외한 모든 화면과 작업에 로그인을 요구한다.
- 첫 관리자는 배포 환경의 `BOM_ADMIN_SETUP_KEY`와 직접 정한 비밀번호로 만든다. 관리자가 하나라도 등록되면 초기 설정 화면은 자동으로 닫힌다.
- 세션은 `BOM_SESSION_SECRET`으로 서명하며 브라우저에 HttpOnly·SameSite 쿠키로 저장한다. Vercel에서는 Secure 쿠키를 사용한다.
- 비밀번호는 PBKDF2-SHA256으로 해시해 저장한다. 새 사용자는 첫 로그인에 임시 비밀번호를 변경한다.
- 계정 Excel 첫 번째 시트에 `email`, `name`, `temporary_password` 열이 필요하다. 이메일·이름·임시 비밀번호의 한글 열 이름도 지원한다. 최대 500명, 파일 2 MB까지 허용한다. 원본 계정 Excel은 서버에 저장하지 않는다.
- POST 요청은 같은 출처인지 확인한다. 공개 계정 가입은 제공하지 않는다.

## 파일 저장 및 제한

- 웹 업로드 원본은 `upload_batches.file_content`와 `drawing_files.file_content`의 PostgreSQL 바이너리 열에 보관한다.
- 업로드 1건당 최대 크기는 4 MB다. Vercel Function 요청 본문 제한보다 작게 유지한다.
- 내보내기·패키지 임시 파일은 Vercel의 `/tmp`에만 저장되며 인스턴스 교체 시 사라질 수 있다.

## Supabase 설정

1. 사용자가 승인한 Supabase 프로젝트를 선택하고, Vercel 런타임용으로 Transaction Pooler(포트 6543) 연결 URL을 준비한다. 가능하면 DDL 권한이 없는 제한된 앱 역할을 사용한다.
2. 배포 전에 Supabase DB 백업을 확인한다. DDL 마이그레이션은 `BOM_MIGRATION_DATABASE_URL`을 로컬에서만 사용해 적용한다.
3. 로컬에서 `python -m alembic upgrade head`와 `python -m alembic current`로 스키마를 갱신·확인한다. 마이그레이션 URL은 Vercel에 등록하지 않는다.
4. Supabase DB 비밀번호를 채팅·문서·Git에 복사하지 않는다. `.env`는 Git에서 제외한다.

## Vercel 설정

- Root Directory: 저장소 루트
- Python 진입점: `api/index.py`; 경로 설정: `vercel.json`
- Production 환경 변수: `BOM_DATABASE_URL`, `BOM_SESSION_SECRET`, `BOM_ADMIN_SETUP_KEY`
- DB URL에는 Transaction Pooler 주소(6543)를 사용한다. `BOM_MIGRATION_DATABASE_URL`과 관리자 DB 암호를 별도로 등록하지 않는다.
- `BOM_APP_DATA_DIR`은 `/tmp/bom-management-service`로 설정한다.
- 최초 배포 후 `/setup-admin`에서 초기 관리자 계정을 만들고 로그인한 다음, 관리자 화면에서 계정 발급이 가능한지 확인한다.

## 변경 이력

| 날짜 | 변경 | 확인 |
|---|---|---|
| 2026-10-16 | 인증형 배포, 로그인·관리자 계정 발급, Excel 일괄 등록, 세션·업로드 보안 규칙 추가 | Supabase/Vercel 배포 전 환경 변수와 계정 범위 확인 |
