"""create ERP transaction and match tables

Revision ID: 20261007_0004
Revises: 20261007_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0004"
down_revision: str | None = "20261007_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "erp_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("upload_batch_id", sa.Integer(), nullable=False),
        sa.Column("part_number", sa.String(length=160), nullable=False),
        sa.Column("normalized_part_number", sa.String(length=160), nullable=False),
        sa.Column("part_name", sa.String(length=300), nullable=True),
        sa.Column("material", sa.String(length=200), nullable=True),
        sa.Column("specification", sa.String(length=300), nullable=True),
        sa.Column("normalized_specification", sa.String(length=300), nullable=False),
        sa.Column("maker", sa.String(length=160), nullable=True),
        sa.Column("supplier", sa.String(length=200), nullable=True),
        sa.Column("item_category", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("ordered_quantity", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("received_quantity", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("delivered_quantity", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("required_quantity", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("planned_delivery_date", sa.Date(), nullable=True),
        sa.Column("revised_delivery_date", sa.Date(), nullable=True),
        sa.Column("erp_updated_at", sa.DateTime(), nullable=True),
        sa.Column("purchase_order_number", sa.String(length=100), nullable=True),
        sa.Column("eco_number", sa.String(length=100), nullable=True),
        sa.Column("erp_version", sa.String(length=50), nullable=True),
        sa.Column("source_data", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["upload_batch_id"], ["upload_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_erp_transactions_project_id", ["project_id"]),
        ("ix_erp_transactions_upload_batch_id", ["upload_batch_id"]),
        ("ix_erp_transactions_part_number", ["part_number"]),
        ("ix_erp_transactions_normalized_part_number", ["normalized_part_number"]),
        ("ix_erp_transactions_normalized_specification", ["normalized_specification"]),
        ("ix_erp_transactions_erp_updated_at", ["erp_updated_at"]),
    ):
        op.create_index(name, "erp_transactions", columns, unique=False)
    op.create_table(
        "erp_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bom_item_id", sa.Integer(), nullable=False),
        sa.Column("erp_transaction_id", sa.Integer(), nullable=False),
        sa.Column("match_method", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("review_type", sa.String(length=30), nullable=True),
        sa.Column("review_evidence", sa.JSON(), nullable=False),
        sa.Column("confirmation_note", sa.Text(), nullable=True),
        sa.Column("confirmed_by", sa.String(length=100), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["bom_item_id"], ["bom_items.id"]),
        sa.ForeignKeyConstraint(["erp_transaction_id"], ["erp_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_erp_matches_bom_item_id", "erp_matches", ["bom_item_id"], unique=False)
    op.create_index(
        "ix_erp_matches_erp_transaction_id", "erp_matches", ["erp_transaction_id"], unique=False
    )
    op.create_index("ix_erp_matches_status", "erp_matches", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_erp_matches_status", table_name="erp_matches")
    op.drop_index("ix_erp_matches_erp_transaction_id", table_name="erp_matches")
    op.drop_index("ix_erp_matches_bom_item_id", table_name="erp_matches")
    op.drop_table("erp_matches")
    for name in (
        "ix_erp_transactions_erp_updated_at",
        "ix_erp_transactions_normalized_specification",
        "ix_erp_transactions_normalized_part_number",
        "ix_erp_transactions_part_number",
        "ix_erp_transactions_upload_batch_id",
        "ix_erp_transactions_project_id",
    ):
        op.drop_index(name, table_name="erp_transactions")
    op.drop_table("erp_transactions")
