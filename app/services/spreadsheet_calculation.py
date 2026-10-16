"""고객 제출 Excel의 수식 계산과 오류 확인을 담당한다."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import load_workbook


class SpreadsheetCalculationError(RuntimeError):
    """계산 엔진 실행 또는 수식 오류로 고객용 출력이 중단된 경우다."""


def find_calculation_engine(configured_path: str | None = None) -> Path | None:
    """설정값, PATH, 표준 Windows 설치 경로 순서로 LibreOffice를 찾는다."""

    explicit_path = configured_path or os.getenv("BOM_CALC_ENGINE_PATH")
    if explicit_path:
        candidates = [explicit_path]
    else:
        candidates = [shutil.which("soffice")]
    candidates.extend(
        [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def validate_calculated_workbook(path: Path) -> None:
    """계산 후 저장된 값에 Excel 오류가 남지 않았는지 확인한다."""

    workbook = load_workbook(path, data_only=True, read_only=True)
    errors: list[str] = []
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("#"):
                    errors.append(f"{sheet.title}!{cell.coordinate}: {cell.value}")
    if errors:
        preview = ", ".join(errors[:10])
        raise SpreadsheetCalculationError(f"견적 양식 수식 오류 {len(errors)}건: {preview}")


def recalculate_workbook(path: Path, *, timeout_seconds: int = 60) -> None:
    """LibreOffice를 별도 프로세스로 실행해 원본 파일을 계산 결과로 교체한다."""

    engine = find_calculation_engine()
    if engine is None:
        raise SpreadsheetCalculationError(
            "LibreOffice 계산 엔진을 찾을 수 없습니다. "
            "설치 후 BOM_CALC_ENGINE_PATH를 soffice.exe 경로로 설정하세요."
        )
    if path.suffix.lower() != ".xlsx":
        raise SpreadsheetCalculationError("현재 계산 엔진은 .xlsx 고객 견적 파일만 지원합니다.")

    with TemporaryDirectory(prefix="bom-calc-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        input_directory = temporary_root / "input"
        output_directory = temporary_root / "output"
        input_directory.mkdir()
        output_directory.mkdir()
        input_path = input_directory / path.name
        shutil.copy2(path, input_path)
        result = subprocess.run(
            [
                str(engine),
                "--headless",
                "--convert-to",
                "xlsx",
                "--outdir",
                str(output_directory),
                str(input_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        calculated_path = output_directory / path.name
        if result.returncode != 0 or not calculated_path.is_file():
            detail = (result.stderr or result.stdout).strip()
            reason = detail or "계산 결과 파일이 생성되지 않았습니다."
            raise SpreadsheetCalculationError(
                f"LibreOffice 계산에 실패했습니다. {reason}"
            )
        shutil.copy2(calculated_path, path)
    validate_calculated_workbook(path)
