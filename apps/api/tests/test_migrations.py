"""Exercise actual migrations and immutable history on the disposable test database."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from careeros.db import Base
from careeros.models import Application, ApplicationEvent, Job
from careeros.seed import seed
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError


def test_migrations_preserve_data_and_enforce_history(db):
    Base.metadata.drop_all(db.bind)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    settings = SimpleNamespace(database_url=db.bind.url.render_as_string(hide_password=False))
    with patch("careeros.config.get_settings", return_value=settings):
        try:
            command.upgrade(config, "head")
            user, _ = seed(db, "migration@example.com", "Migration-test-only-123")
            job = db.scalar(select(Job).where(Job.user_id == user.id).limit(1))
            application = Application(user_id=user.id, job_id=job.id, status="SAVED", data={})
            application.events.append(ApplicationEvent(status="SAVED", note="Original"))
            db.add(application)
            db.commit()
            event_id = application.events[0].id
            for statement in (
                "UPDATE application_events SET note='changed' WHERE id=:id",
                "DELETE FROM application_events WHERE id=:id",
            ):
                with pytest.raises(DBAPIError, match="append-only"):
                    with db.begin_nested():
                        db.execute(text(statement), {"id": event_id})
            assert (
                db.scalar(
                    text("SELECT note FROM application_events WHERE id=:id"), {"id": event_id}
                )
                == "Original"
            )
            db.commit()
            command.downgrade(config, "8f22a1")
            command.upgrade(config, "head")
            assert db.scalar(text("SELECT count(*) FROM jobs")) == 8
            db.commit()
            command.check(config)
        finally:
            db.rollback()
            command.downgrade(config, "base")
            db.execute(text("DROP TABLE alembic_version"))
            db.commit()
