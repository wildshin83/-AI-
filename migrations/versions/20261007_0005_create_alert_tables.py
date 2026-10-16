# ruff: noqa: E501
"""create price and alert tables

Revision ID: 20261007_0005
Revises: 20261007_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0005"
down_revision: str | None = "20261007_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bom_item_id", sa.Integer(), nullable=False),
        sa.Column("erp_transaction_id", sa.Integer(), nullable=True),
        sa.Column("price_type", sa.String(length=30), nullable=False),
        sa.Column("amount", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("basis_date", sa.Date(), nullable=True),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("confirmed_by", sa.String(length=100), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["bom_item_id"], ["bom_items.id"]),
        sa.ForeignKeyConstraint(["erp_transaction_id"], ["erp_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_price_records_bom_item_id", ["bom_item_id"]),
        ("ix_price_records_erp_transaction_id", ["erp_transaction_id"]),
        ("ix_price_records_price_type", ["price_type"]),
        ("ix_price_records_is_confirmed", ["is_confirmed"]),
    ):
        op.create_index(name, "price_records", columns, unique=False)
    op.create_table(
        "item_alert_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bom_item_id", sa.Integer(), nullable=False),
        sa.Column("is_critical", sa.Boolean(), nullable=False),
        sa.Column("price_increase_rate", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("long_lead_days", sa.Integer(), nullable=True),
        sa.Column("overdue_days", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["bom_item_id"], ["bom_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bom_item_id"),
    )
    op.create_index(
        "ix_item_alert_rules_bom_item_id", "item_alert_rules", ["bom_item_id"], unique=False
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("bom_item_id", sa.Integer(), nullable=True),
        sa.Column("alert_code", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=200), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["bom_item_id"], ["bom_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_alerts_project_id", ["project_id"]),
        ("ix_alerts_bom_item_id", ["bom_item_id"]),
        ("ix_alerts_alert_code", ["alert_code"]),
        ("ix_alerts_status", ["status"]),
        ("ix_alerts_source_fingerprint", ["source_fingerprint"]),
    ):
        op.create_index(name, "alerts", columns, unique=False)
    op.create_table(
        "alert_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("action_status", sa.String(length=30), nullable=False),
        sa.Column("actor_name", sa.String(length=100), nullable=False),
        sa.Column("action_note", sa.Text(), nullable=False),
        sa.Column("alternative_reviewed", sa.Boolean(), nullable=True),
        sa.Column("expected_resolution_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_actions_alert_id", "alert_actions", ["alert_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_alert_actions_alert_id", table_name="alert_actions")
    op.drop_table("alert_actions")
    for name in (
        "ix_alerts_source_fingerprint",
        "ix_alerts_status",
        "ix_alerts_alert_code",
        "ix_alerts_bom_item_id",
        "ix_alerts_project_id",
    ):
        op.drop_index(name, table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_item_alert_rules_bom_item_id", table_name="item_alert_rules")
    op.drop_table("item_alert_rules")
    for name in (
        "ix_price_records_is_confirmed",
        "ix_price_records_price_type",
        "ix_price_records_erp_transaction_id",
        "ix_price_records_bom_item_id",
    ):
        op.drop_index(name, table_name="price_records")
    op.drop_table("price_records")
