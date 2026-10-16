# Supabase PostgreSQL 연결 지침

## 1. 목적과 적용 범위

팀원 PC에서 실행하는 FastAPI 앱을 Supabase PostgreSQL에 연결하는 설정 절차다. Supabase Auth와 Storage는 사용하지 않는다. 로컬 앱은 도면·원본·첨부 파일을 PC별 로컬 저장소에 남기며, Vercel 공개 테스트 배포는 업로드 원본만 PostgreSQL 바이너리 열에 저장한다.

현재 앱은 `BOM_DATABASE_URL`이 설정되면 PostgreSQL을 사용하고, 설정이 없으면 기존 개발용 SQLite를 사용한다. 원격 DB를 적용한 뒤 `/health?details=true`에서 `database`가 `postgresql`인지 확인한다.

## 2. 책임과 사전 확인

- DB 프로젝트 생성·접속 권한·백업 정책: Supabase 프로젝트 관리자
- 런타임 DB 역할·연결 문자열 보관과 실행: 앱을 실행하는 담당자
- 스키마 변경용 관리자 연결 문자열 사용: 마이그레이션 담당자, 마이그레이션 실행 시간으로 제한
- 고객·ERP 실데이터 연결 전 회사 보안정책 및 데이터 처리 승인 범위 확인: 프로젝트 책임자
- 개인별 인증을 구현하지 않으므로 현 구조는 DB 접속 사용자를 앱 사용자로 구분하지 않는다. 공유 DB 접속정보의 배포·회수 방법과 최소 권한 역할은 실제 팀 배포 전에 별도로 확정한다.

## 3. 연결 설정

1. Supabase Dashboard에서 프로젝트를 열고 **Connect**에서 PostgreSQL 연결 문자열을 가져온다. 이 앱처럼 오래 실행되는 FastAPI 프로세스는 직접 연결을 사용할 수 있고, 직접 연결이 네트워크에서 지원되지 않으면 Session pooler 연결 문자열을 사용한다. Transaction pooler를 선택하는 경우 앱은 psycopg prepared statement를 비활성화한다.
2. 앱 런타임에는 테이블 조회·추가·수정·삭제 권한만 가진 별도 DB 역할을 사용한다. PostgreSQL 관리자 암호를 일반 앱 연결로 사용하지 않는다. 사용자 인증이 없으므로 앱 사용자는 공용 DB 역할과 동일한 데이터 접근 범위를 갖는다.
3. 암호에 예약 문자가 있으면 URL 인코딩한 연결 문자열을 사용한다. 연결 암호를 채팅, Git, 문서, 로그, 화면 캡처에 붙여 넣지 않는다.
4. 프로젝트 루트의 `.env` 파일 또는 앱 프로세스 환경에 런타임 URL을 다음 이름으로 설정한다.

```text
BOM_DATABASE_URL=postgresql://<사용자>:<인코딩된 암호>@<Supabase 호스트>:<포트>/postgres
```

5. 스키마 생성·변경에는 별도의 `BOM_MIGRATION_DATABASE_URL`을 일시적으로 제공한다. 관리자 URL은 일반 앱용 `.env`에 저장하지 않고 마이그레이션 실행 시간에만 사용한다. `run_local.ps1`은 이 변수가 없으면 Supabase 마이그레이션을 건너뛰고 기존 스키마로 앱을 실행한다.
6. 앱은 `postgresql://` 연결 문자열을 psycopg 3 드라이버 형식으로 변환하고, 명시하지 않은 경우 `sslmode=require`를 적용한다. Transaction pooler 호환을 위해 psycopg prepared statement를 비활성화한다.
7. `.env`는 `.gitignore`에 포함되어 있지만, 원격 저장소나 Windows 실행 패키지에 넣지 않는다. 프로젝트의 DB 비밀번호가 노출되면 Supabase Dashboard에서 즉시 변경하고 기존 문자열을 폐기한다.

Supabase SQL Editor에서 아래와 같이 앱 역할 권한을 구성할 수 있다. 이 예는 앱 전용 프로젝트의 `public` 스키마를 전제로 하며, 관리자 암호는 SQL을 적용한 뒤 `BOM_DATABASE_URL`에 쓰지 않는다.

```sql
CREATE ROLE bom_app LOGIN PASSWORD '<강력한-임의-암호>';
GRANT CONNECT ON DATABASE postgres TO bom_app;
GRANT USAGE ON SCHEMA public TO bom_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bom_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO bom_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bom_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO bom_app;
```

앱 역할은 `BOM_DATABASE_URL`에, 스키마 업그레이드용 관리자 연결은 마이그레이션을 실행하는 동안에만 `BOM_MIGRATION_DATABASE_URL`에 제공한다. 별도 스키마나 마이그레이션 소유자를 사용하면 위 권한과 default privileges를 실제 소유 역할에 맞게 조정한다.

Supabase는 지속 실행되는 앱에는 직접 연결을 권장하고, IPv4 전용 네트워크에서는 Session pooler를 대안으로 안내한다. `sslmode=require`는 연결을 암호화하지만 서버 인증서의 호스트 검증까지 하지는 않는다. 운영 보안 기준이 요구하면 Supabase 인증서를 사용해 `sslmode=verify-full`과 `sslrootcert`를 설정한다. 연결 방식과 SSL 설정은 Supabase의 [Postgres 연결 안내](https://supabase.com/docs/guides/database/connecting-to-postgres)를 따른다.

## 4. 마이그레이션 및 실행

1. 프로젝트 Python 환경을 설치·갱신한다. `psycopg[binary]`와 `python-dotenv`는 프로젝트 의존성에 포함되어 있다.
2. 관리자 연결 URL을 마이그레이션 명령에만 일시 주입하고 `python -m alembic upgrade head`를 실행한다. 완료 후 `BOM_MIGRATION_DATABASE_URL`을 제거한다. 이후 실행은 런타임 전용 `BOM_DATABASE_URL`만 사용한다.
3. `run_local.ps1`은 로컬 SQLite에서는 마이그레이션을 적용한다. Supabase에서는 `BOM_MIGRATION_DATABASE_URL`이 주어진 경우에만 스키마를 갱신하고, 없으면 원격 DDL을 건너뛴다.
4. 브라우저에서 `/health?details=true`를 열고 응답의 `status`가 `ok`, `database`가 `postgresql`인지 확인한다. 기본 `/health` 응답 형식은 기존 모니터링 호환을 위해 유지한다.
5. 연결 실패 시 DB 호스트·포트·암호 인코딩·네트워크 방화벽·SSL 설정을 확인한다. 연결 문자열 전체를 로그나 문의에 복사하지 않는다.

마이그레이션은 현재 테이블 구조를 Supabase DB에 생성한다. 로컬 SQLite의 기존 업무 데이터는 자동 복사하거나 삭제하지 않는다. 실제 이관이 필요한 경우 양쪽 DB의 백업, 충돌·행 수 대조, 파일 경로 처리 계획을 세운 뒤 별도 이관 절차를 승인하고 실행한다.

## 5. 백업·복구 및 파일 처리

- PostgreSQL 연결 상태에서 앱의 로컬 SQLite 백업·복원 메뉴는 비활성화되며, API도 SQLite ZIP을 원격 DB에 복원하지 못하게 차단한다.
- Supabase PostgreSQL 백업·복구는 Supabase 프로젝트의 별도 운영 절차를 사용한다. 담당자, 보존 주기, 복구 목표, 실제 복구 리허설은 실데이터 파일럿 전에 확정한다.
- 로컬 앱 첨부 파일은 각 PC에 남기므로 Supabase DB 백업만으로 복구되지 않는다. PC 교체·파일 공유 시나리오와 로컬 첨부 백업을 별도로 관리한다.
- Vercel 테스트 배포는 업로드 원본을 DB에 저장하므로 DB 백업에 포함된다. 이 방식은 테스트 파일에 한정하고, 파일당 최대 크기 4MB를 지킨다.

## 6. 변경 이력

| 일자 | 변경 내용 | 확인 주체 |
|---|---|---|
| 2026-10-16 | Supabase PostgreSQL 연결, 환경변수, SSL, 마이그레이션과 백업 범위 최초 작성 | CS사업부 기술팀 |
