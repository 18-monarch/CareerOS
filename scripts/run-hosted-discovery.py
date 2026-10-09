"""Run discovery without exposing private database/provider output in public CI logs."""

import os
import subprocess
import sys
from urllib.parse import parse_qs, urlsplit


def valid_config(environ):
    try:
        database = urlsplit(environ.get("DATABASE_URL", ""))
        origin = urlsplit(environ.get("FRONTEND_ORIGIN", ""))
        return bool(
            database.scheme in ("postgres", "postgresql", "postgresql+psycopg")
            and database.hostname
            and "-pooler" not in database.hostname
            and database.username
            and database.password
            and database.path.strip("/")
            and parse_qs(database.query).get("sslmode", [None])[0]
            in ("require", "verify-ca", "verify-full")
            and origin.scheme == "https"
            and origin.hostname
            and not origin.username
            and not origin.password
            and not origin.path
            and not origin.query
            and not origin.fragment
        )
    except ValueError:
        return False


def run_cycle():
    # Do not forward stdout/stderr or upload it as an artifact: this repository
    # can be public, and database exceptions may include private record values.
    try:
        result = subprocess.run(
            [sys.executable, "-m", "careeros.deploy", "cron"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=900,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        print("Discovery could not finish. Check cloud configuration and CareerOS Sources.")
        return 1
    if result.returncode:
        print("Discovery reported an error. Check database access and CareerOS Sources health.")
        return 1
    print("Worker completed. Open CareerOS Sources to see due checks and imported opportunities.")
    return 0


def main():
    if not valid_config(os.environ):
        print(
            "Configure CAREEROS_DATABASE_URL as a direct PostgreSQL TLS secret and "
            "FRONTEND_ORIGIN as your HTTPS site origin (no trailing slash)."
        )
        return 1
    return run_cycle()


if __name__ == "__main__":
    raise SystemExit(main())
