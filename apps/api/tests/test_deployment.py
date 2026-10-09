from unittest.mock import patch

import pytest
from careeros.cloud_account import create_account, validate_url
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


def test_cloud_account_targets_migrated_database_and_preserves_existing_user(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path}/account.db")
    upgrade_database(engine)
    identifier = create_account(engine, "cloud@example.com", "A-long-cloud-password", "Cloud")
    with pytest.raises(ValueError, match="already exists"):
        create_account(engine, "cloud@example.com", "Different-password-123", "Changed")
    with engine.connect() as conn:
        assert (
            conn.scalar(text("SELECT name FROM users WHERE id=:id"), {"id": identifier}) == "Cloud"
        )
        assert conn.scalar(text("SELECT count(*) FROM jobs")) == 0
    with engine.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num='old'"))
    with pytest.raises(ValueError, match="Deploy the current"):
        create_account(engine, "another@example.com", "A-long-cloud-password", "Another")
    for value in (
        "sqlite:///local.db",
        "postgresql://u:p@ep-pooler.neon.tech/db?sslmode=require",
        "postgresql://u:p@ep.neon.tech/db",
    ):
        with pytest.raises(ValueError):
            validate_url(value)
    assert validate_url("postgresql://u:p@ep.neon.tech/db?sslmode=require")
    engine.dispose()
