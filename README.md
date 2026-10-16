# BOM 관리 서비스

CS사업부 기술팀용 로컬 설치형 BOM·ERP·견적 검토 서비스입니다.

## 설계 기준

- 각 사용자 PC에서 독립 실행합니다.
- 데이터는 로컬 SQLite DB와 앱 데이터 폴더에 저장합니다.
- Excel 원본, 도면, 가격 확정, 견적 제출본은 변경 이력과 함께 보존합니다.
- ERP 후보값은 자동 적용하지 않습니다.
- 고객 출력물과 내부 원가 정보는 분리합니다.

상세 요구사항은 `prd.md`, 실제 Excel 열 매핑과 제약은 `EXCEL_MAPPING_RULES.md`, 구현 진행 상태는 `plan.md`를 참조합니다.

## 참고자료

`참고자료/` 폴더에는 Inventor BOM, ERP BOM, LGES 고객 견적 양식 원본을 보관합니다. 서비스의 고객 견적 출력은 이 폴더의 양식을 사용하며, Windows 실행 패키지를 만들 때도 함께 포함됩니다. 원본 파일을 교체할 때는 먼저 `CUSTOMER_QUOTE_TEMPLATE_RULES.md`와 매핑 규칙을 검토합니다.

## 로컬 데이터 경로

기본 데이터 경로는 Windows의 `%LOCALAPPDATA%\\BomManagementService`입니다.

- `data/`: SQLite DB
- `files/`: 업로드 원본 및 첨부 파일
- `exports/`: 생성한 Excel 출력물
- `backups/`: 백업 파일
- `logs/`: 실행 로그

## 개발 실행

개발용 Python 환경을 준비한 뒤 다음 명령으로 실행합니다.

```powershell
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

브라우저에서 `http://127.0.0.1:8765/health`로 상태를 확인할 수 있습니다.

### Windows 실행

개발 환경에서는 아래 명령으로 DB 마이그레이션 후 서비스를 시작합니다.

```powershell
.\run_local.ps1
```

별도 로컬 데이터 경로가 필요하면 `-DataDirectory` 인수로 지정합니다. Windows 실행 파일 패키지는 `build_windows.ps1`로 생성하며, 생성 전에는 인터넷 연결이 가능한 사내 승인 환경에서 PyInstaller 설치가 필요합니다.

### 고객 견적 Excel 계산

고객 견적은 LibreOffice Calc로 수식을 계산하고 오류를 검사한 뒤에만 생성됩니다. 설치·경로 설정·검증 절차는 `CALCULATION_ENGINE_GUIDE.md`를 따릅니다.

## 파일럿과 백업

- 실제 업무 파일럿 절차는 `TEST_SCENARIOS.md`를 따른다.
- 프로젝트 패키지는 새 프로젝트로만 가져올 수 있으며, 동일 프로젝트 번호는 자동 병합·덮어쓰기를 하지 않는다.
- 백업 복원은 기존 로컬 DB·첨부 파일을 바꾸므로, ZIP 선택과 `RESTORE` 확인 문구를 요구하고 복원 직전 상태를 자동 백업한다. 상세 절차는 `BACKUP_RESTORE_GUIDE.md`를 따른다.
