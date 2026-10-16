# ruff: noqa: E501
"""create drawing file table

Revision ID: 20261007_0007
Revises: 20261007_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0007"
down_revision: str | None = "20261007_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drawing_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("bom_item_id", sa.Integer(), nullable=True),
        sa.Column("bom_revision_id", sa.Integer(), nullable=True),
        sa.Column("drawing_number", sa.String(length=160), nullable=False),
        sa.Column("drawing_revision", sa.String(length=80), nullable=True),
        sa.Column("file_type", sa.String(length=30), nullable=False),
        sa.Column("original_file_name", sa.String(length=300), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("uploaded_by", sa.String(length=100), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["bom_item_id"], ["bom_items.id"]),
        sa.ForeignKeyConstraint(["bom_revision_id"], ["bom_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_drawing_files_project_id", ["project_id"]),
        ("ix_drawing_files_bom_item_id", ["bom_item_id"]),
        ("ix_drawing_files_bom_revision_id", ["bom_revision_id"]),
        ("ix_drawing_files_drawing_number", ["drawing_number"]),
        ("ix_drawing_files_file_type", ["file_type"]),
    ):
        op.create_index(name, "drawing_files", columns, unique=False)


def downgrade() -> None:
    for name in (
        "ix_drawing_files_file_type",
        "ix_drawing_files_drawing_number",
        "ix_drawing_files_bom_revision_id",
        "ix_drawing_files_bom_item_id",
        "ix_drawing_files_project_id",
    ):
        op.drop_index(name, table_name="drawing_files")
    op.drop_table("drawing_files")
