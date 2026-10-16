"""고객 판매 견적의 품목·총액 계산 규칙."""

from __future__ import annotations

from decimal import Decimal

from app.models.quotes import QuoteItem


def customer_unit_price(item: QuoteItem) -> Decimal:
    """가공품은 3개 구성비 합계, 구매품은 품목 판매단가를 사용한다."""

    if item.item_type == "machined":
        return item.material_cost + item.machining_cost + item.treatment_cost
    return item.purchased_unit_price


def customer_item_amount(item: QuoteItem) -> Decimal:
    return customer_unit_price(item) * item.quantity
