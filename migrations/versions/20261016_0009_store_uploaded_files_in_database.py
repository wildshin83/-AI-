"""store uploaded workbooks and drawings in postgres-compatible byte columns

Revision ID: 20261016_0009
Revises: 20261007_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261016_0009"
down_revision: str | None = "20261007_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("upload_batches", sa.Column("file_content", sa.LargeBinary(), nullable=True))
    op.add_column("drawing_files", sa.Column("file_content", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("drawing_files", "file_content")
    op.drop_column("upload_batches", "file_content")
