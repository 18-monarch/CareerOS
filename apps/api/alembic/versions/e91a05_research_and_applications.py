"""Research inbox and application drafts."""

import sqlalchemy as sa
from alembic import op

revision = "e91a05"
down_revision = "d82f04"
branch_labels = None
depends_on = None


def upgrade():
    for table, unique in (("research_leads", "url_key"), ("application_drafts", "job_id")):
        cols = [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("data", sa.JSON(), nullable=False),
        ]
        if table == "research_leads":
            cols += [
                sa.Column("url_key", sa.String(64), nullable=False),
                sa.Column("url", sa.Text(), nullable=False),
            ]
        else:
            cols += [
                sa.Column(
                    "job_id",
                    sa.String(36),
                    sa.ForeignKey("jobs.id", ondelete="CASCADE"),
                    nullable=False,
                )
            ]
        op.create_table(table, *cols, sa.UniqueConstraint("user_id", unique))
        op.create_index("ix_" + table + "_user_id", table, ["user_id"])


def downgrade():
    op.drop_table("application_drafts")
    op.drop_table("research_leads")
