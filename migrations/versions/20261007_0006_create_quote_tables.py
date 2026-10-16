# ruff: noqa: E501
"""create quote version tables

Revision ID: 20261007_0006
Revises: 20261007_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0006"
down_revision: str | None = "20261007_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quote_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("bom_revision_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("submission_date", sa.DateTime(), nullable=True),
        sa.Column("submission_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["bom_revision_id"], ["bom_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "version_number"),
    )
    op.create_index("ix_quote_versions_project_id", "quote_versions", ["project_id"], unique=False)
    op.create_index("ix_quote_versions_status", "quote_versions", ["status"], unique=False)
    op.create_table(
        "quote_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_version_id", sa.Integer(), nullable=False),
        sa.Column("bom_item_id", sa.Integer(), nullable=True),
        sa.Column("drawing_number", sa.String(length=160), nullable=False),
        sa.Column("item_name", sa.String(length=300), nullable=True),
        sa.Column("item_type", sa.String(length=30), nullable=True),
        sa.Column("material", sa.String(length=200), nullable=True),
        sa.Column("treatment", sa.String(length=200), nullable=True),
        sa.Column("specification", sa.String(length=300), nullable=True),
        sa.Column("maker", sa.String(length=160), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("material_cost", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("machining_cost", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("treatment_cost", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("purchased_unit_price", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["quote_version_id"], ["quote_versions.id"]),
        sa.ForeignKeyConstraint(["bom_item_id"], ["bom_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_quote_items_quote_version_id", "quote_items", ["quote_version_id"], unique=False
    )
    op.create_index(
        "ix_quote_items_drawing_number", "quote_items", ["drawing_number"], unique=False
    )
    op.create_table(
        "quote_adjustments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_version_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("amount", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["quote_version_id"], ["quote_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_quote_adjustments_quote_version_id",
        "quote_adjustments",
        ["quote_version_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_quote_adjustments_quote_version_id", table_name="quote_adjustments")
    op.drop_table("quote_adjustments")
    op.drop_index("ix_quote_items_drawing_number", table_name="quote_items")
    op.drop_index("ix_quote_items_quote_version_id", table_name="quote_items")
    op.drop_table("quote_items")
    op.drop_index("ix_quote_versions_status", table_name="quote_versions")
    op.drop_index("ix_quote_versions_project_id", table_name="quote_versions")
    op.drop_table("quote_versions")
