# Vercel 공개 테스트 배포

## 목적과 범위

로그인 없이 BOM 업로드·검토·수정 흐름을 시연하기 위한 공개 테스트 배포 절차다. 누구나 화면의 데이터를 읽고 변경할 수 있으므로 가상 데이터만 포함하는 별도 Supabase 테스트 프로젝트에 연결한다. 업무용 프로젝트, 실제 고객·거래처 자료, 회사 원본 파일을 연결하지 않는다.

## 파일 보관 및 제한

- 웹 업로드 원본은 `upload_batches.file_content`와 `drawing_files.file_content`의 PostgreSQL 바이너리 열에 보관한다.
- 업로드 1건당 최대 크기는 4MB다. Vercel Function의 요청 본문 제한을 넘기지 않도록 여유를 둔다.
- Vercel 배포에서는 Excel·도면 이외의 내보내기 파일과 패키지 파일은 `/tmp`에서만 생성된다. 인스턴스가 교체되면 사라질 수 있으므로 장기 보관물로 취급하지 않는다.
- 공개 폼에는 사용자 인증이나 업로드 작성자 검증이 없다. 테스트 데이터를 주기적으로 초기화하고, 배포 종료 후 Vercel 도메인을 비활성화한다.

## Supabase 사전 준비

1. 기존 업무 DB와 별도로 무료 테스트용 Supabase 프로젝트를 만든다. 조직이 결제를 요구하거나 유료 플랜 선택이 표시되면 진행하지 않는다.
2. 런타임 연결은 해당 프로젝트의 Transaction Pooler 주소(포트 6543)를 사용한다. `BOM_DATABASE_URL`만 애플리케이션 런타임에 설정한다.
3. 마이그레이션은 테스트 프로젝트에만 적용한다. 로컬 PowerShell에서 `BOM_DATABASE_URL`과 임시 `BOM_MIGRATION_DATABASE_URL`을 준비한 뒤 `python -m app.migrate`를 실행한다.
4. Vercel에는 별도 쓰기 전용 런타임 역할의 Transaction Pooler URL을 `BOM_DATABASE_URL` 환경 변수로 등록한다. `postgres` 관리자 암호나 `BOM_MIGRATION_DATABASE_URL`은 Vercel에 등록하지 않는다.
5. `VERCEL_DEMO_DATABASE_URL` 등 이름을 정해 테스트 프로젝트의 URL을 로컬 `.env`에만 보관하고, 기존 `.env`를 덮어쓰지 않는다.

## Vercel 설정

- Root Directory: 저장소 루트
- Build/Output: `requirements.txt`, `vercel.json`, `api/index.py` 자동 인식
- Environment Variable: `BOM_DATABASE_URL` (Production/Preview 모두 별도 테스트 DB URL)
- `BOM_APP_DATA_DIR`은 `vercel.json`에서 `/tmp/bom-management-service`로 설정된다.
- 배포 URL은 테스트 참가자에게 전달하기 전에 이름·단가·거래처 등 가상 데이터만 있는지 확인한다.

## 운영 중지와 데이터 초기화

테스트 종료 시 Vercel 프로젝트의 배포 별칭을 제거하거나 프로젝트를 일시 중지한다. DB의 샘플 초기화는 테스트 DB로 연결한 것을 다시 확인한 뒤 별도 작업으로 수행한다. 이 문서는 데이터 삭제를 자동으로 실행하지 않는다.

## 변경 이력

| 날짜 | 변경 | 확인 |
|---|---|---|
| 2026-10-16 | 로그인 없는 공개 테스트 배포 설정과 DB 원본 파일 저장 절차 추가 | Vercel 요청 본문·파일시스템 제약을 고려한 코드 준비 |
