"""제출 견적 차수 간 고객 판매 금액 변화를 비교한다."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.quote_calculation import customer_item_amount
from app.models.quotes import QuoteItem


@dataclass(frozen=True)
class QuoteItemChange:
    drawing_number: str
    change_type: str
    before_amount: Decimal
    after_amount: Decimal


def compare_quote_items(before: list[QuoteItem], after: list[QuoteItem]) -> list[QuoteItemChange]:
    """도면번호를 기준으로 고객 견적의 추가·삭제·금액 변화를 계산한다."""

    before_by_number = {item.drawing_number: item for item in before}
    after_by_number = {item.drawing_number: item for item in after}
    changes: list[QuoteItemChange] = []
    for number in sorted(before_by_number.keys() | after_by_number.keys()):
        previous = before_by_number.get(number)
        current = after_by_number.get(number)
        previous_amount = customer_item_amount(previous) if previous else Decimal("0")
        current_amount = customer_item_amount(current) if current else Decimal("0")
        if previous is None:
            changes.append(QuoteItemChange(number, "추가", previous_amount, current_amount))
        elif current is None:
            changes.append(QuoteItemChange(number, "삭제", previous_amount, current_amount))
        elif previous_amount != current_amount or previous.quantity != current.quantity:
            changes.append(QuoteItemChange(number, "변경", previous_amount, current_amount))
    return changes
