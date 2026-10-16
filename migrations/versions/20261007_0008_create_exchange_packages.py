"""create exchange package table

Revision ID: 20261007_0008
Revises: 20261007_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0008"
down_revision: str | None = "20261007_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exchange_packages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("package_type", sa.String(length=30), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exchange_packages_project_id", "exchange_packages", ["project_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_exchange_packages_project_id", table_name="exchange_packages")
    op.drop_table("exchange_packages")
