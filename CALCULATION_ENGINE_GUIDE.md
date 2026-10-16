# 고객 견적 Excel 계산 엔진 설치·운영 지침

## 1. 목적과 적용 범위

고객 제출용 LGES 견적 Excel은 수식으로 소계·일반관리비·이윤·최종 합계를 계산한다. `openpyxl`은 수식을 기록할 수 있지만 계산하지 못하므로, 서비스는 로컬 LibreOffice Calc를 계산 엔진으로 실행한 뒤 수식 오류를 검사한다.

적용 대상은 **고객 견적 Excel 출력**이다. BOM·구매 협의·원가 집계처럼 수식이 없는 내부 목록에는 적용하지 않는다.

## 2. 설치 방법

1. IT 또는 보안 담당 승인 후 각 사용자 PC에 LibreOffice를 설치한다. 기본 설치 경로를 유지하는 것을 권장한다.
2. 서비스는 아래 순서로 `soffice.exe`를 찾는다.
   - 환경 변수 `BOM_CALC_ENGINE_PATH`
   - Windows `PATH`의 `soffice`
   - `C:\Program Files\LibreOffice\program\soffice.exe`
   - `C:\Program Files (x86)\LibreOffice\program\soffice.exe`
3. 기본 경로가 아닌 경우 PowerShell에서 다음처럼 사용자 환경 변수로 등록한 뒤 서비스를 다시 실행한다.

```powershell
[Environment]::SetEnvironmentVariable(
  "BOM_CALC_ENGINE_PATH",
  "D:\Apps\LibreOffice\program\soffice.exe",
  "User"
)
```

## 3. 서비스 동작

1. 서비스가 원본 고객 양식을 복사해 판매 견적 입력 셀만 채운다.
2. LibreOffice를 백그라운드 모드로 실행해 별도 임시 폴더에서 계산한다.
3. 계산된 파일의 `#DIV/0!`, `#VALUE!` 등 수식 오류를 검사한다.
4. 오류가 없을 때만 고객 견적 파일을 다운로드한다. 엔진이 없거나 수식 오류가 있으면 생성 중 파일을 폐기하고 원인을 화면에 표시한다.

## 4. 파일럿 확인 항목

- 고객 견적 Excel 1건을 생성해 Excel에서 소계·일반관리비·이윤·최종 합계가 보이는지 확인한다.
- 가공품의 재질/가공/후처리 3개 행 합계가 서비스 판매 견적금액과 일치하는지 확인한다.
- 고객 출력에 거래처·ERP 매입단가·내부 관리단가가 없는지 확인한다.
- 오류 발생 시 고객에게 해당 파일을 전달하지 않고, 원본 양식/입력 행/수식을 검토한다.

## 5. 책임과 제한

- 설치와 업데이트는 사내 IT·보안 정책에 따른다.
- 계산 엔진은 금액 계산 오류를 찾는 보조 장치이며, 제출 책임자는 최종 견적금액을 검토한다.
- LibreOffice와 Microsoft Excel의 호환성 차이가 의심되면 Excel에서 최종 열람 검증을 추가한다.

## 6. 변경 이력

| 일자 | 변경 내용 | 확인 주체 |
|---|---|---|
| 2026-10-07 | LibreOffice 기반 로컬 계산·수식 오류 검사 운영 기준 최초 작성 | CS사업부 기술팀 |
