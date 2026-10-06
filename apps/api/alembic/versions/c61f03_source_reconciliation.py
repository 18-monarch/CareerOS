"""Track disappearance separately for every source occurrence."""

import sqlalchemy as sa
from alembic import op

revision = "c61f03"
down_revision = "8f22a1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "job_source_occurrences",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "job_source_occurrences",
        sa.Column("missing_runs", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "source_health", sa.Column("closed", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade():
    op.drop_column("source_health", "closed")
    op.drop_column("job_source_occurrences", "missing_runs")
    op.drop_column("job_source_occurrences", "is_active")
