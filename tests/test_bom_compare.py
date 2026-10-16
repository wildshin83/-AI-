from decimal import Decimal

from app.domain.bom_compare import BomComparableItem, compare_bom_revisions


def item(number: str, *, quantity: str = "1", material: str = "SUS304") -> BomComparableItem:
    return BomComparableItem(number, number, material, None, None, None, Decimal(quantity))


def test_compare_bom_revisions_reports_add_remove_and_changes() -> None:
    changes = compare_bom_revisions(
        [item("A"), item("B"), item("C", material="A6061")],
        [item("A", quantity="2"), item("C", material="SUS304"), item("D")],
    )

    assert [(change.change_type, change.drawing_number) for change in changes] == [
        ("삭제", "B"),
        ("추가", "D"),
        ("수량 변경", "A"),
        ("사양 변경", "C"),
    ]
