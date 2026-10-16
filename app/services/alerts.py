"""단가·납기 위험을 공통 규칙으로 계산하고 조치 이력을 남긴다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alerts import Alert, AlertAction, ItemAlertRule, PriceRecord
from app.models.bom import BomItem, BomRevision
from app.models.erp import ErpMatch, ERPTransaction
from app.models.settings import Setting
from app.services.audit import record_audit

DEFAULT_RULES = {
    "price_increase_rate": "0.05",
    "long_lead_days": "28",
    "delivery_warning_offsets": "7,3,1,0",
    "delivery_overdue_days": "0",
}


@dataclass(frozen=True)
class AlertCandidate:
    alert_code: str
    severity: str
    title: str
    details: dict[str, str]
    fingerprint: str
    due_date: date | None = None


def _setting_value(session: Session, key: str) -> str:
    setting = session.scalar(select(Setting).where(Setting.key == key))
    if setting is None:
        setting = Setting(
            key=key,
            value=DEFAULT_RULES[key],
            value_type="number" if key != "delivery_warning_offsets" else "csv",
            description="BOM 경고 엔진 기본값",
        )
        session.add(setting)
        session.flush()
    return setting.value


def _item_rule(session: Session, item: BomItem) -> ItemAlertRule | None:
    return session.scalar(select(ItemAlertRule).where(ItemAlertRule.bom_item_id == item.id))


def _effective_price_rate(session: Session, item: BomItem) -> Decimal:
    item_rule = _item_rule(session, item)
    if item_rule and item_rule.price_increase_rate is not None:
        return Decimal(item_rule.price_increase_rate)
    return Decimal(_setting_value(session, "price_increase_rate"))


def _effective_due_date(transaction: ERPTransaction) -> date | None:
    return transaction.revised_delivery_date or transaction.planned_delivery_date


def _is_unreceived(transaction: ERPTransaction) -> bool:
    if transaction.ordered_quantity is None:
        return False
    delivered = transaction.received_quantity or transaction.delivered_quantity or Decimal("0")
    return delivered < transaction.ordered_quantity


def _item_transactions(session: Session, item: BomItem, *, as_of: date) -> list[ERPTransaction]:
    cutoff = datetime.combine(as_of - timedelta(days=365), time.min)
    return list(
        session.scalars(
            select(ERPTransaction)
            .join(ErpMatch, ErpMatch.erp_transaction_id == ERPTransaction.id)
            .where(
                ErpMatch.bom_item_id == item.id,
                ErpMatch.status == "applied",
                ERPTransaction.erp_updated_at >= cutoff,
            )
            .order_by(ERPTransaction.erp_updated_at.desc(), ERPTransaction.id.desc())
        )
    )


def build_alert_candidates(
    session: Session, *, item: BomItem, as_of: date | None = None
) -> list[AlertCandidate]:
    """현재 ERP 양식으로 계산 가능한 위험만 반환한다.

    발주일·실제 입고일이 없는 경우 실적 리드타임·과거 납기 지연은 의도적으로 계산하지 않는다.
    """

    today = as_of or date.today()
    transactions = _item_transactions(session, item, as_of=today)
    candidates: list[AlertCandidate] = []
    if not transactions:
        candidates.append(
            AlertCandidate(
                "no_recent_erp_history",
                "warning",
                "최근 1년 내 확정 ERP 이력이 없습니다.",
                {"drawing_number": item.drawing_number},
                "no-recent-history",
            )
        )
        return candidates

    newest = transactions[0]
    confirmed_internal_price = session.scalar(
        select(PriceRecord)
        .where(
            PriceRecord.bom_item_id == item.id,
            PriceRecord.price_type == "internal_management",
            PriceRecord.is_confirmed.is_(True),
        )
        .order_by(PriceRecord.confirmed_at.desc(), PriceRecord.id.desc())
    )
    if (
        newest.unit_price is not None
        and confirmed_internal_price is not None
        and newest.unit_price != confirmed_internal_price.amount
    ):
        candidates.append(
            AlertCandidate(
                "price_recheck_needed",
                "warning",
                "확정 내부 관리단가와 최신 ERP 후보 단가가 달라 재검토가 필요합니다.",
                {
                    "erp_reference_price": str(newest.unit_price),
                    "confirmed_internal_price": str(confirmed_internal_price.amount),
                },
                f"recheck:{newest.id}:{confirmed_internal_price.id}",
            )
        )
    if newest.unit_price is not None:
        price_records = list(
            session.scalars(
                select(PriceRecord)
                .where(
                    PriceRecord.bom_item_id == item.id,
                    PriceRecord.price_type == "erp_reference",
                    PriceRecord.erp_transaction_id != newest.id,
                )
                .order_by(PriceRecord.basis_date.desc(), PriceRecord.id.desc())
            )
        )
        previous = next((entry for entry in price_records if entry.amount > 0), None)
        if previous is not None:
            increase_rate = (newest.unit_price - previous.amount) / previous.amount
            if increase_rate > _effective_price_rate(session, item):
                candidates.append(
                    AlertCandidate(
                        "erp_price_increase",
                        "warning",
                        "ERP 후보 단가가 비교 이력 대비 상승했습니다.",
                        {
                            "current_price": str(newest.unit_price),
                            "previous_price": str(previous.amount),
                            "increase_rate": str(increase_rate),
                        },
                        f"price:{newest.id}:{previous.id}",
                    )
                )

    due_date = _effective_due_date(newest)
    if due_date and _is_unreceived(newest):
        overdue_days = int(_setting_value(session, "delivery_overdue_days"))
        offset_values = _setting_value(session, "delivery_warning_offsets").split(",")
        offsets = {int(value.strip()) for value in offset_values}
        days_to_due = (due_date - today).days
        if days_to_due < -overdue_days:
            candidates.append(
                AlertCandidate(
                    "delivery_overdue",
                    "critical",
                    "미입고 품목의 예정 납기일이 경과했습니다.",
                    {"effective_due_date": due_date.isoformat(), "days_overdue": str(-days_to_due)},
                    f"due:{newest.id}:{due_date.isoformat()}",
                    due_date,
                )
            )
        elif days_to_due in offsets:
            candidates.append(
                AlertCandidate(
                    "delivery_due_soon",
                    "warning",
                    "미입고 품목의 예정 납기일이 임박했습니다.",
                    {"effective_due_date": due_date.isoformat(), "days_to_due": str(days_to_due)},
                    f"due:{newest.id}:{due_date.isoformat()}:{days_to_due}",
                    due_date,
                )
            )
    return candidates


def refresh_project_alerts(
    session: Session, *, project_id: int, as_of: date | None = None
) -> list[Alert]:
    """ERP 갱신 시 확정 단가를 바꾸지 않고 후보/경고만 최신화한다."""

    revisions = list(
        session.scalars(
            select(BomRevision)
            .where(BomRevision.project_id == project_id)
            .order_by(BomRevision.id.desc())
        )
    )
    if not revisions:
        return []
    latest_revision = revisions[0]
    results: list[Alert] = []
    for item in session.scalars(
        select(BomItem).where(BomItem.bom_revision_id == latest_revision.id)
    ):
        for candidate in build_alert_candidates(session, item=item, as_of=as_of):
            existing = session.scalar(
                select(Alert).where(
                    Alert.bom_item_id == item.id,
                    Alert.alert_code == candidate.alert_code,
                    Alert.source_fingerprint == candidate.fingerprint,
                )
            )
            if existing is None:
                existing = Alert(
                    project_id=project_id,
                    bom_item_id=item.id,
                    alert_code=candidate.alert_code,
                    severity=candidate.severity,
                    title=candidate.title,
                    details=candidate.details,
                    source_fingerprint=candidate.fingerprint,
                    due_date=candidate.due_date,
                )
                session.add(existing)
            else:
                existing.severity = candidate.severity
                existing.title = candidate.title
                existing.details = candidate.details
                existing.due_date = candidate.due_date
            results.append(existing)
    session.flush()
    record_audit(
        session,
        action="alerts.refreshed",
        entity_type="project",
        entity_id=project_id,
        details={"alert_count": len(results)},
    )
    session.commit()
    return results


def update_alert_status(
    session: Session,
    *,
    alert: Alert,
    status: str,
    actor_name: str,
    action_note: str,
    alternative_reviewed: bool | None = None,
    expected_resolution_date: date | None = None,
) -> AlertAction:
    """상태 변경과 근거를 원자적으로 저장한다."""

    allowed = {"acknowledged", "in_progress", "resolved", "exception_approved"}
    if status not in allowed:
        raise ValueError("지원하지 않는 경고 상태입니다.")
    if status in {"resolved", "exception_approved"} and not action_note.strip():
        raise ValueError("해결 또는 예외 승인에는 근거 메모가 필요합니다.")
    if not actor_name.strip() or not action_note.strip():
        raise ValueError("담당자와 조치 내용은 필수입니다.")
    action = AlertAction(
        alert_id=alert.id,
        action_status=status,
        actor_name=actor_name.strip(),
        action_note=action_note.strip(),
        alternative_reviewed=alternative_reviewed,
        expected_resolution_date=expected_resolution_date,
    )
    alert.status = status
    session.add(action)
    session.flush()
    record_audit(
        session,
        action="alert.status_changed",
        entity_type="alert",
        entity_id=alert.id,
        actor_name=actor_name.strip(),
        details={"status": status},
    )
    session.commit()
    return action
