"""Explicit hosted entry point: migrate under a lock, then start API or cron."""

import argparse
import os
import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config

from careeros.db import engine
from careeros.services.locking import job_lock


def upgrade_database(target_engine, timeout=45):
    config_path = Path.cwd() / "alembic.ini"
    if not config_path.is_file():
        raise RuntimeError("Start CareerOS from the repository root (alembic.ini is required).")
    config = Config(str(config_path))
    config.set_main_option("script_location", str(config_path.parent / "apps/api/alembic"))
    until = time.monotonic() + timeout
    while True:
        with job_lock(target_engine, "schema-upgrade") as acquired:
            if acquired:
                with target_engine.begin() as connection:
                    config.attributes["connection"] = connection
                    command.upgrade(config, "head")
                return
        if time.monotonic() >= until:
            raise RuntimeError(
                "Another deployment holds the migration lock; retry this deployment."
            )
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["api", "cron", "migrate"])
    args = parser.parse_args()
    upgrade_database(engine)
    engine.dispose()
    if args.mode == "migrate":
        return
    if args.mode == "cron":
        import asyncio
        import json

        from worker.__main__ import run

        async def cycle():
            # Expiry also removes expired auth sessions; discovery owns all personalized alerts.
            expiry = await run("expire-jobs")
            discovery = await run("discover-jobs")
            return {
                "expiry": expiry,
                "discovery": discovery,
                "errors": expiry.get("errors", 0) + discovery.get("errors", 0),
            }

        result = asyncio.run(cycle())
        print(json.dumps(result))
        raise SystemExit(1 if result["errors"] else 0)
    port = int(os.getenv("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "careeros.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
        ],
    )


if __name__ == "__main__":
    main()
