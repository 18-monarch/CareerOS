"""Persist automatic discovery schedules and filtered source counts."""

import sqlalchemy as sa
from alembic import op

revision = "d82f04"
down_revision = "c61f03"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "discovery_state",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_started", sa.DateTime()),
        sa.Column("last_finished", sa.DateTime()),
        sa.Column("next_run", sa.DateTime()),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(240)),
    )
    op.add_column(
        "source_health", sa.Column("skipped", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade():
    op.drop_column("source_health", "skipped")
    op.drop_table("discovery_state")
