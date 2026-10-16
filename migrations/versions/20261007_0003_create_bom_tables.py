"""create bom tables

Revision ID: 20261007_0003
Revises: 20261007_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0003"
down_revision: str | None = "20261007_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bom_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("upload_batch_id", sa.Integer(), nullable=False),
        sa.Column("revision_name", sa.String(length=80), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["upload_batch_id"], ["upload_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("upload_batch_id"),
    )
    op.create_index("ix_bom_revisions_project_id", "bom_revisions", ["project_id"], unique=False)
    op.create_table(
        "bom_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bom_revision_id", sa.Integer(), nullable=False),
        sa.Column("source_item_number", sa.String(length=80), nullable=True),
        sa.Column("drawing_number", sa.String(length=160), nullable=False),
        sa.Column("normalized_drawing_number", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("component", sa.String(length=300), nullable=True),
        sa.Column("material", sa.String(length=200), nullable=True),
        sa.Column("treatment", sa.String(length=200), nullable=True),
        sa.Column("specification", sa.String(length=300), nullable=True),
        sa.Column("maker", sa.String(length=160), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("item_type", sa.String(length=30), nullable=True),
        sa.Column("source_data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["bom_revision_id"], ["bom_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bom_items_bom_revision_id", "bom_items", ["bom_revision_id"], unique=False)
    op.create_index("ix_bom_items_drawing_number", "bom_items", ["drawing_number"], unique=False)
    op.create_index(
        "ix_bom_items_normalized_drawing_number",
        "bom_items",
        ["normalized_drawing_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bom_items_normalized_drawing_number", table_name="bom_items")
    op.drop_index("ix_bom_items_drawing_number", table_name="bom_items")
    op.drop_index("ix_bom_items_bom_revision_id", table_name="bom_items")
    op.drop_table("bom_items")
    op.drop_index("ix_bom_revisions_project_id", table_name="bom_revisions")
    op.drop_table("bom_revisions")
