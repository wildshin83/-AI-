"""회사 프로젝트 코드 약호와 번호 조합 규칙."""

from __future__ import annotations

import re
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project

PROJECT_TYPES = {
    "E": "장비(Equipment)",
    "I": "개선/변경(Improvement)",
    "P": "부품 판매(Parts Sales)",
    "M": "상품 판매(Merchandize)",
    "S": "용역/서비스(Service)",
    "R": "연구개발(R&D)",
    "U": "Unit",
    "Z": "공통/기타",
}
CUSTOMER_CODES = {
    "LGES": "LGE",
    "LG PRI": "LGP",
    "신진 남경법인": "SJC",
}
CUSTOMER_OPTIONS = tuple(CUSTOMER_CODES)
SITE_CODES = {
    "OC1": "OC1",
    "NJ1": "NJ1",
    "NA1": "NA1",
    "NB1": "NB1",
    "WA1": "WA1",
    "WA3": "WA3",
    "UC1": "Ultium Cells Ohio",
    "UC2": "Ultium Cells Tennessee",
    "UC3": "Ultium Cells 3공장",
    "MI1": "ESMI Holland 1공장",
    "MI2": "ESMI Holland 2공장",
    "MI3": "ESMI Lansing",
    "ST1": "ST1",
    "HD1": "HD1",
    "DNJ": "DNJ",
    "EWA": "EWA",
    "ETC": "ETC",
}
EQUIPMENT_CODES = {
    "EL": "Lamination 적층부",
    "EH": "Lamination 적층부(H/C)",
    "LA": "Lamination 전극",
    "LH": "Lamination 전극(H/C)",
    "EN": "Notching 적층부",
    "NC": "Notching 전극",
    "FS": "FFS",
    "OW": "Over-Wrap",
    "ME": "MEA 적층기",
    "MS": "MEA 조립/검사",
    "BM": "BAG Making",
    "DN": "DNC",
    "NT": "NTC",
    "NN": "NNC",
    "ET": "기타",
}
LINE_CODES = tuple(f"{number:02}" for number in range(11))
UNIT_CODES = tuple(f"{number:02}" for number in range(4))
YEARS = tuple(str(year)[-2:] for year in range(2023, 2031))
DEPARTMENT_CODES = {
    "M": "기구(Mechanical)",
    "E": "전장(Electrical)",
    "C": "CS(Customer Support)",
    "S": "SF(Smart Factory)",
    "V": "머신비전(Machine Vision)",
    "L": "필름비전(Film Vision)",
    "F": "필름(Film)",
    "N": "VNE Vision",
    "P": "VNE PLC",
    "Q": "품질(Quality)",
}
MAIN_PROJECT_CODES = {"T": "Mother PJT", "M": "Main PJT", "S": "Sub PJT", "I": "Indep(독립) PJT"}
ORDER_CODES = {
    "": "미적용",
    "A": "유상",
    "B": "무상",
    "P": "유상(부품)",
    "M": "유지보수",
}


class ProjectCodeError(ValueError):
    """선택된 약호가 회사 기준서에 없거나 번호를 만들 수 없다."""


def _choice(value: str, choices: Mapping[str, str] | tuple[str, ...], label: str) -> str:
    if value not in choices:
        raise ProjectCodeError(f"{label}을(를) 기준서의 목록에서 선택하세요.")
    return value


def _numeric_code(value: str, *, digits: int, minimum: int, maximum: int, label: str) -> str:
    if not re.fullmatch(rf"\d{{{digits}}}", value) or not minimum <= int(value) <= maximum:
        raise ProjectCodeError(
            f"{label}은(는) {minimum:0{digits}}~{maximum:0{digits}} 범위의 "
            f"{digits}자리 숫자여야 합니다."
        )
    return value


def project_code_base(selection: Mapping[str, str]) -> str:
    """PJT+고객+사이트-설비+연도-라인+호기+부서+Main 유형 조합."""
    project_type = _choice(selection.get("project_type", ""), PROJECT_TYPES, "프로젝트 구분")
    customer = _choice(selection.get("customer_name", ""), CUSTOMER_CODES, "고객사")
    site = _choice(selection.get("site_code", ""), SITE_CODES, "사이트")
    equipment = _choice(selection.get("equipment_code", ""), EQUIPMENT_CODES, "설비 구분")
    year = _numeric_code(
        selection.get("award_year", ""), digits=2, minimum=23, maximum=30, label="수주연도"
    )
    line = _numeric_code(
        selection.get("line_code", ""), digits=2, minimum=0, maximum=10, label="라인 번호"
    )
    unit = _numeric_code(
        selection.get("unit_code", ""), digits=2, minimum=0, maximum=3, label="호기 번호"
    )
    department = _choice(selection.get("department_code", ""), DEPARTMENT_CODES, "부서")
    main = _choice(selection.get("main_project_code", ""), MAIN_PROJECT_CODES, "Main PJT 구분")
    return (
        f"{project_type}{CUSTOMER_CODES[customer]}{site}-{equipment}{year}-"
        f"{line}{unit}{department}{main}"
    )


def suggest_project_number(session: Session, selection: Mapping[str, str]) -> str:
    """선택값으로 번호를 만들고 같은 약호·연도 내 다음 주문 순번을 제안한다."""
    base = project_code_base(selection)
    order_code = _choice(selection.get("order_code", ""), ORDER_CODES, "유무상 구분")
    if not order_code:
        return base

    prefix = f"{base}-{order_code}"
    existing = session.scalars(
        select(Project.project_number).where(Project.project_number.like(f"{prefix}%"))
    )
    used = {
        int(match.group(1))
        for number in existing
        if (match := re.fullmatch(re.escape(prefix) + r"(\d{3})", number))
    }
    selected_serial = selection.get("order_serial", "")
    if selected_serial:
        _numeric_code(selected_serial, digits=3, minimum=0, maximum=999, label="주문 순번")
        if int(selected_serial) in used:
            raise ProjectCodeError("이미 사용 중인 순번입니다. 다른 3자리 숫자를 입력하세요.")
        serial = int(selected_serial)
    else:
        serial = next((candidate for candidate in range(1, 1000) if candidate not in used), None)
        if serial is None:
            raise ProjectCodeError("해당 번호 조합의 순번 999개가 모두 사용되었습니다.")
    return f"{prefix}{serial:03}"
