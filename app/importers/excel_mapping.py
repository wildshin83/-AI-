"""실제 Inventor·ERP Excel 양식을 위한 공통 열 매핑·검증 엔진."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path
from typing import Any


class WorkbookKind(StrEnum):
    INVENTOR_BOM = "inventor_bom"
    ERP_BOM = "erp_bom"


@dataclass(frozen=True)
class FieldRule:
    field: str
    aliases: tuple[str, ...]
    required: bool = False


@dataclass(frozen=True)
class MappingIssue:
    severity: str
    message: str
    row: int | None = None
    column: str | None = None


@dataclass(frozen=True)
class MappingPreview:
    workbook_kind: WorkbookKind
    sheet_name: str
    header_row: int
    mapping: dict[str, str]
    unmapped_headers: list[str]
    issues: list[MappingIssue]


INVENTOR_RULES = (
    FieldRule("item_number", ("항목",)),
    FieldRule("bom_structure", ("bom구조", "bom 구조")),
    FieldRule("quantity", ("수량", "qty"), required=True),
    FieldRule("file_name", ("파일이름", "파일 이름")),
    FieldRule("drawing_number", ("부품번호", "부품 번호", "도면번호", "도번"), required=True),
    FieldRule("title", ("제목",)),
    FieldRule("component", ("component", "품명")),
    FieldRule("material", ("material", "재질")),
    FieldRule("treatment", ("treatment", "후처리")),
    FieldRule("specification", ("specification", "규격")),
    FieldRule("maker", ("maker", "메이커", "제조사")),
    FieldRule("author", ("작성자",)),
    FieldRule("engineering_approver", ("엔지니어링승인자", "엔지니어링 승인자")),
    FieldRule("mass", ("질량",)),
    FieldRule("source_note", ("비고", "비 고")),
    FieldRule("source_date", ("date", "작성일")),
    FieldRule("source_project_number", ("projectno", "project no.", "project no")),
    FieldRule("stock_number", ("스톡번호", "스톡 번호")),
)

ERP_RULES = (
    FieldRule("project_number", ("프로젝트번호", "프로젝트 번호"), required=True),
    FieldRule("part_number", ("품번", "부품번호", "부품 번호"), required=True),
    FieldRule("part_name", ("품명", "부품명")),
    FieldRule("material", ("재질",)),
    FieldRule("specification", ("규격",)),
    FieldRule("supplier", ("구매발주거래처", "거래처")),
    FieldRule("ordered_quantity", ("구매발주수량", "발주수량")),
    FieldRule("received_quantity", ("구매입고수량", "입고수량")),
    FieldRule("planned_delivery_date", ("납품예정일", "예상납기일")),
    FieldRule("revised_delivery_date", ("변경납품예정일(scm)", "변경 납품 예정일(scm)")),
    FieldRule("erp_updated_at", ("최종수정일",)),
    FieldRule("purchase_order_number", ("구매발주번호", "발주번호")),
    FieldRule("eco_number", ("eco번호", "eco 번호")),
    FieldRule("erp_version", ("버전", "rev")),
    FieldRule("treatment", ("후처리",)),
    FieldRule("maker", ("메이커", "maker", "제조사")),
    FieldRule("item_category", ("품목분류", "품목 분류"), required=True),
    FieldRule("required_quantity", ("총소요량", "소요량")),
    FieldRule("unit", ("기준단위", "단위")),
    FieldRule("unit_price", ("발주단가", "단가")),
    FieldRule("order_amount", ("발주금액", "금액")),
    FieldRule("purchasing_stop", ("구매중단여부", "구매 중단 여부")),
    FieldRule("delivered_quantity", ("구매납품수량", "납품수량")),
    FieldRule("purchase_request_number", ("구매요청번호", "요청번호")),
    FieldRule("purchase_approval_number", ("구매품의번호", "품의번호")),
    FieldRule("receipt_number", ("구매입고번호", "입고번호")),
    FieldRule("source_note", ("비고",)),
    FieldRule("location", ("location", "위치")),
    FieldRule("approver", ("승인자",)),
    FieldRule("distributor", ("배포자",)),
)


def normalize_header(value: Any) -> str:
    """열 제목의 공백·대소문자·전각 차이를 제거해 비교한다."""

    if value is None:
        return ""
    return "".join(str(value).strip().lower().split())


def rules_for(workbook_kind: WorkbookKind) -> tuple[FieldRule, ...]:
    """업로드 유형별 표준 필드 규칙을 반환한다."""

    return INVENTOR_RULES if workbook_kind == WorkbookKind.INVENTOR_BOM else ERP_RULES


def _find_header_row(rows: list[tuple[Any, ...]], workbook_kind: WorkbookKind) -> int:
    required_aliases = {
        alias for rule in rules_for(workbook_kind) if rule.required for alias in rule.aliases
    }
    normalized_required = {normalize_header(alias) for alias in required_aliases}

    best_row = 0
    best_score = -1
    for row_index, row in enumerate(rows, start=1):
        score = len({normalize_header(value) for value in row} & normalized_required)
        if score > best_score:
            best_row = row_index
            best_score = score
    return best_row


def preview_mapping(path: Path | BytesIO, workbook_kind: WorkbookKind) -> MappingPreview:
    """원본을 변경하지 않고 헤더와 자동 매핑 결과를 확인한다."""

    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook.active
    rows = list(worksheet.iter_rows(min_row=1, max_row=10, values_only=True))
    header_row = _find_header_row(rows, workbook_kind)
    headers = list(rows[header_row - 1]) if rows else []
    indexed_headers = {
        normalize_header(header): str(header).strip()
        for header in headers
        if normalize_header(header)
    }

    mapping: dict[str, str] = {}
    issues: list[MappingIssue] = []
    used_headers: set[str] = set()
    for rule in rules_for(workbook_kind):
        matched_header = next(
            (
                indexed_headers[normalize_header(alias)]
                for alias in rule.aliases
                if normalize_header(alias) in indexed_headers
            ),
            None,
        )
        if matched_header:
            mapping[rule.field] = matched_header
            used_headers.add(matched_header)
        elif rule.required:
            issues.append(
                MappingIssue(
                    severity="error",
                    message=f"필수 열 '{rule.field}'을(를) 찾지 못했습니다.",
                    row=header_row,
                )
            )

    unmapped_headers = [
        str(header).strip()
        for header in headers
        if header and str(header).strip() not in used_headers
    ]
    return MappingPreview(
        workbook_kind=workbook_kind,
        sheet_name=worksheet.title,
        header_row=header_row,
        mapping=mapping,
        unmapped_headers=unmapped_headers,
        issues=issues,
    )


def validate_mapping(mapping: dict[str, str], workbook_kind: WorkbookKind) -> list[MappingIssue]:
    """사용자가 수정한 매핑에서 필수 필드가 빠지지 않았는지 확인한다."""

    return [
        MappingIssue(severity="error", message=f"필수 필드 '{rule.field}'의 열을 지정하세요.")
        for rule in rules_for(workbook_kind)
        if rule.required and not mapping.get(rule.field)
    ]
