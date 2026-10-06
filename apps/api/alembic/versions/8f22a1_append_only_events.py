"""Enforce application history immutability at the database boundary."""

from alembic import op

revision = "8f22a1"
down_revision = "92052cb75924"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION careeros_immutable_event() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Application event history is append-only'; END; $$""")
        op.execute(
            "CREATE TRIGGER immutable_application_events BEFORE UPDATE OR DELETE ON application_events FOR EACH ROW EXECUTE FUNCTION careeros_immutable_event()"
        )
    else:
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER immutable_events_{action.lower()} BEFORE {action} ON application_events BEGIN SELECT RAISE(ABORT, 'Application event history is append-only'); END"
            )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER immutable_application_events ON application_events")
        op.execute("DROP FUNCTION careeros_immutable_event()")
    else:
        op.execute("DROP TRIGGER immutable_events_update")
        op.execute("DROP TRIGGER immutable_events_delete")
