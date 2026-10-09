"""Upgrade local SQLite safely before starting workers, with an online SQLite backup."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from careeros.config import get_settings
from careeros.services.locking import job_lock
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

SCHEMA_HEAD = "e91a05"


def schema_revision(engine):
    try:
        with engine.connect() as conn:
            return conn.scalar(text("SELECT version_num FROM alembic_version"))
    except SQLAlchemyError:
        return None


def migrate_local(engine):
    settings = get_settings()
    if (
        settings.environment != "development"
        or not settings.auto_migrate_local
        or engine.dialect.name != "sqlite"
    ):
        return
    if not engine.url.database or engine.url.database == ":memory:":
        return
    with job_lock(engine, "schema-upgrade") as acquired:
        if not acquired:
            raise RuntimeError(
                "Another CareerOS process is upgrading the database; restart shortly."
            )
        if schema_revision(engine) == SCHEMA_HEAD:
            return
        dbpath = Path(engine.url.database).resolve()
        if dbpath.exists() and dbpath.stat().st_size:
            target = dbpath.with_name(
                dbpath.name + ".backup-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
            )
            with sqlite3.connect(dbpath) as source, sqlite3.connect(target) as backup:
                source.backup(backup)
        root = Path(__file__).resolve().parents[4]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "apps/api/alembic"))
        # Migration uses the exact active engine, independent of working directory.
        with engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "head")
