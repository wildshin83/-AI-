"""ORM 모델을 한곳에서 불러와 Alembic이 전체 메타데이터를 인식하게 한다."""

from app.models.alerts import Alert, AlertAction, ItemAlertRule, PriceRecord
from app.models.audit import AuditLog
from app.models.auth import AccountRequest, AuthUser
from app.models.bom import BomItem, BomRevision
from app.models.drawings import DrawingFile
from app.models.erp import ErpMatch, ERPTransaction
from app.models.imports import MappingProfile, UploadBatch
from app.models.packages import ExchangePackage
from app.models.project import Project, ProjectStatus
from app.models.quotes import QuoteAdjustment, QuoteItem, QuoteVersion
from app.models.schedules import ScheduleChangeRequest
from app.models.settings import Setting

__all__ = [
    "AuthUser",
    "AccountRequest",
    "AuditLog",
    "Alert",
    "AlertAction",
    "BomItem",
    "BomRevision",
    "DrawingFile",
    "ExchangePackage",
    "ERPTransaction",
    "ErpMatch",
    "ItemAlertRule",
    "MappingProfile",
    "Project",
    "ProjectStatus",
    "PriceRecord",
    "QuoteAdjustment",
    "QuoteItem",
    "QuoteVersion",
    "Setting",
    "ScheduleChangeRequest",
    "UploadBatch",
]
