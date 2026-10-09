from unittest.mock import patch

import pytest
from careeros.config import Settings
from careeros.db import build_engine
from careeros.deploy import upgrade_database
from careeros.services import discovery
from careeros.services.locking import job_lock
from careeros.services.startup import SCHEMA_HEAD
from sqlalchemy import text


def test_hosted_startup_migrates_idempotently_and_preserves_data(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path}/deploy.db")
    upgrade_database(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id,name,email,password_hash,created_at,updated_at,is_admin) VALUES ('keep','Keep','keep@example.com','unused',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,0)"
            )
        )
    upgrade_database(engine)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == SCHEMA_HEAD
        assert conn.scalar(text("SELECT name FROM users WHERE id='keep'")) == "Keep"
    with job_lock(engine, "schema-upgrade") as locked:
        assert locked
        with pytest.raises(RuntimeError, match="migration lock"):
            upgrade_database(engine, timeout=0)
    engine.dispose()


def test_hosted_discovery_can_queue_with_local_scheduler_disabled(logged, db, user):
    settings = Settings(auto_discovery_enabled=False, external_discovery_enabled=True)
    with patch.object(discovery, "get_settings", return_value=settings):
        data = logged.get("/discovery").json()
        assert data["scheduler_enabled"] is True
        assert data["scheduler_mode"] == "external"
        assert data["worker_interval_minutes"] == 60
        assert logged.post("/discovery/refresh").status_code == 202
        assert discovery.ensure_state(db, user.id).next_run is None
