"""두 BOM Rev의 품목 변경을 화면·출력에서 공통으로 계산한다."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BomComparableItem:
    drawing_number: str
    normalized_drawing_number: str
    material: str | None
    treatment: str | None
    specification: str | None
    maker: str | None
    quantity: Decimal


@dataclass(frozen=True)
class BomChange:
    change_type: str
    drawing_number: str
    changed_fields: tuple[str, ...]


COMPARE_FIELDS = ("material", "treatment", "specification", "maker", "quantity")


def compare_bom_revisions(
    previous: Iterable[BomComparableItem], current: Iterable[BomComparableItem]
) -> list[BomChange]:
    """도면번호 기준으로 추가·삭제·사양·수량 변경을 계산한다."""

    previous_by_key = {item.normalized_drawing_number: item for item in previous}
    current_by_key = {item.normalized_drawing_number: item for item in current}
    changes: list[BomChange] = []
    for key in sorted(previous_by_key.keys() - current_by_key.keys()):
        changes.append(BomChange("삭제", previous_by_key[key].drawing_number, ()))
    for key in sorted(current_by_key.keys() - previous_by_key.keys()):
        changes.append(BomChange("추가", current_by_key[key].drawing_number, ()))
    for key in sorted(previous_by_key.keys() & current_by_key.keys()):
        before, after = previous_by_key[key], current_by_key[key]
        fields = tuple(
            field for field in COMPARE_FIELDS if getattr(before, field) != getattr(after, field)
        )
        if fields:
            change_type = "수량 변경" if fields == ("quantity",) else "사양 변경"
            changes.append(BomChange(change_type, after.drawing_number, fields))
    return changes
