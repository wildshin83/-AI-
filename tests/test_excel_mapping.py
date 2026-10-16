"""실제 Inventor·ERP 열 이름을 기준으로 한 매핑 엔진 테스트."""

from pathlib import Path

from openpyxl import Workbook

from app.importers.excel_mapping import WorkbookKind, preview_mapping


def write_workbook(path: Path, rows: list[list[object]]) -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    return path


def test_inventor_mapping_uses_part_number_as_primary_key(tmp_path: Path) -> None:
    path = write_workbook(
        tmp_path / "inventor.xlsx",
        [
            [
                "항목",
                "수량",
                "부품 번호",
                "COMPONENT",
                "MATERIAL",
                "TREATMENT",
                "SPECIFICATION",
                "MAKER",
            ]
        ],
    )

    preview = preview_mapping(path, WorkbookKind.INVENTOR_BOM)

    assert preview.header_row == 1
    assert preview.mapping["drawing_number"] == "부품 번호"
    assert preview.mapping["quantity"] == "수량"
    assert preview.issues == []


def test_erp_mapping_finds_second_row_header_and_expected_dates(tmp_path: Path) -> None:
    path = write_workbook(
        tmp_path / "erp.xlsx",
        [
            ["프로젝트재료자원진행현황(멀티)(S)"],
            ["프로젝트번호", "품번", "품목분류", "납품예정일", "변경납품예정일(SCM)", "발주단가"],
        ],
    )

    preview = preview_mapping(path, WorkbookKind.ERP_BOM)

    assert preview.header_row == 2
    assert preview.mapping["part_number"] == "품번"
    assert preview.mapping["revised_delivery_date"] == "변경납품예정일(SCM)"
    assert preview.mapping["unit_price"] == "발주단가"
    assert preview.issues == []


def test_mapping_reports_missing_required_columns(tmp_path: Path) -> None:
    path = write_workbook(tmp_path / "invalid.xlsx", [["품명", "규격"]])

    preview = preview_mapping(path, WorkbookKind.ERP_BOM)

    assert {issue.severity for issue in preview.issues} == {"error"}
    assert len(preview.issues) == 3
