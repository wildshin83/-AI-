"""create upload tables

Revision ID: 20261007_0002
Revises: 20261007_0001
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0002"
down_revision: str | None = "20261007_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mapping_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("mapping", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type"),
    )
    op.create_index(
        "ix_mapping_profiles_source_type", "mapping_profiles", ["source_type"], unique=False
    )
    op.create_table(
        "upload_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("original_file_name", sa.String(length=300), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("sheet_name", sa.String(length=150), nullable=True),
        sa.Column("header_row", sa.Integer(), nullable=True),
        sa.Column("mapping", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_upload_batches_project_id", "upload_batches", ["project_id"], unique=False)
    op.create_index(
        "ix_upload_batches_source_type", "upload_batches", ["source_type"], unique=False
    )
    op.create_index("ix_upload_batches_status", "upload_batches", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_upload_batches_status", table_name="upload_batches")
    op.drop_index("ix_upload_batches_source_type", table_name="upload_batches")
    op.drop_index("ix_upload_batches_project_id", table_name="upload_batches")
    op.drop_table("upload_batches")
    op.drop_index("ix_mapping_profiles_source_type", table_name="mapping_profiles")
    op.drop_table("mapping_profiles")
