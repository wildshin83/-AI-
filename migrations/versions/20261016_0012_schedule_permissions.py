"""add user levels and project schedule approvals"""

import sqlalchemy as sa
from alembic import op

revision = "20261016_0012"
down_revision = "20261016_0011"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("auth_users") as batch:
        batch.add_column(sa.Column("permission_level", sa.Integer(), nullable=False,
                                   server_default="1"))
        batch.create_check_constraint("ck_user_level", "permission_level IN (1, 2)")
    op.execute(sa.text("UPDATE auth_users SET permission_level=2 WHERE is_admin=true"))
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("incoming_date", sa.Date()))
        batch.add_column(sa.Column("fob_date", sa.Date()))
        batch.add_column(sa.Column("schedule_version", sa.Integer(), nullable=False,
                                   server_default="1"))
        batch.create_check_constraint("ck_schedule_version", "schedule_version > 0")
    op.create_table(
        "schedule_change_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("auth_users.id"), nullable=False),
        sa.Column("requested_by_name", sa.String(120), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        *[sa.Column(f"{prefix}_{field}", sa.Date()) for prefix in ("old", "proposed")
          for field in ("target_delivery_date", "incoming_date", "fob_date")],
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("auth_users.id")),
        sa.Column("reviewed_by_name", sa.String(120)),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("review_comment", sa.Text()),
        sa.CheckConstraint("status IN ('pending','approved','rejected','conflicted')",
                           name="ck_schedule_request_status"),
        sa.CheckConstraint("base_version > 0", name="ck_request_base_version"),
    )
    op.create_index("ix_schedule_request_project_status", "schedule_change_requests",
                    ["project_id", "status"])
    op.create_index("ix_schedule_request_requester", "schedule_change_requests",
                    ["requested_by_id", "created_at"])


def downgrade():
    op.drop_table("schedule_change_requests")
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("ck_schedule_version", type_="check")
        for name in ("schedule_version", "fob_date", "incoming_date"):
            batch.drop_column(name)
    with op.batch_alter_table("auth_users") as batch:
        batch.drop_constraint("ck_user_level", type_="check")
        batch.drop_column("permission_level")
