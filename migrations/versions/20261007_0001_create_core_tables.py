"""create core project tables

Revision ID: 20261007_0001
Revises:
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("actor_name", sa.String(length=120), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"], unique=False)
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"], unique=False)

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_number", sa.String(length=100), nullable=False),
        sa.Column("project_name", sa.String(length=200), nullable=False),
        sa.Column("customer_name", sa.String(length=160), nullable=False),
        sa.Column("equipment_unit", sa.String(length=160), nullable=False),
        sa.Column("manager_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("target_delivery_date", sa.Date(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_number"),
    )
    op.create_index("ix_projects_customer_name", "projects", ["customer_name"], unique=False)
    op.create_index("ix_projects_is_archived", "projects", ["is_archived"], unique=False)
    op.create_index("ix_projects_manager_name", "projects", ["manager_name"], unique=False)
    op.create_index("ix_projects_project_name", "projects", ["project_name"], unique=False)
    op.create_index("ix_projects_project_number", "projects", ["project_number"], unique=False)
    op.create_index("ix_projects_status", "projects", ["status"], unique=False)
    op.create_index(
        "ix_projects_target_delivery_date", "projects", ["target_delivery_date"], unique=False
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(length=30), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_settings_key", "settings", ["key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_settings_key", table_name="settings")
    op.drop_table("settings")
    op.drop_index("ix_projects_target_delivery_date", table_name="projects")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_project_number", table_name="projects")
    op.drop_index("ix_projects_project_name", table_name="projects")
    op.drop_index("ix_projects_manager_name", table_name="projects")
    op.drop_index("ix_projects_is_archived", table_name="projects")
    op.drop_index("ix_projects_customer_name", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
