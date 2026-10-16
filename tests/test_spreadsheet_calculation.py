"""고객 견적 수식 계산 엔진의 발견·오류 검증 테스트."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from app.services.spreadsheet_calculation import (
    SpreadsheetCalculationError,
    find_calculation_engine,
    recalculate_workbook,
    validate_calculated_workbook,
)


def test_engine_lookup_returns_none_for_missing_configured_path() -> None:
    assert find_calculation_engine(r"C:\not-found\soffice.exe") is None


def test_recalculation_requires_a_local_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workbook_path = tmp_path / "quote.xlsx"
    Workbook().save(workbook_path)
    monkeypatch.setattr(
        "app.services.spreadsheet_calculation.find_calculation_engine", lambda: None
    )

    with pytest.raises(SpreadsheetCalculationError, match="찾을 수 없습니다"):
        recalculate_workbook(workbook_path)


def test_calculated_workbook_rejects_formula_error_values(tmp_path: Path) -> None:
    workbook_path = tmp_path / "broken.xlsx"
    workbook = Workbook()
    workbook.active["A1"] = "#DIV/0!"
    workbook.save(workbook_path)

    with pytest.raises(SpreadsheetCalculationError, match="수식 오류"):
        validate_calculated_workbook(workbook_path)
