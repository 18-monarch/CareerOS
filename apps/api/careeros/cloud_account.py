"""Create a private hosted account without editing your local .env or opening registration."""

import argparse
import getpass

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from careeros.db import build_engine
from careeros.manage import manage_user
from careeros.services.startup import SCHEMA_HEAD


def validate_url(value):
    url = make_url(value)
    if url.drivername not in ("postgres", "postgresql", "postgresql+psycopg"):
        raise ValueError("Use a PostgreSQL connection URL.")
    if not url.host or not url.database or not url.username or not url.password:
        raise ValueError("Copy the complete direct connection URL from Neon.")
    if "-pooler" in url.host:
        raise ValueError("Disable connection pooling in Neon and copy the direct URL.")
    if url.query.get("sslmode") not in ("require", "verify-ca", "verify-full"):
        raise ValueError("The cloud connection must include sslmode=require or stricter.")
    return value


def create_account(engine, email, password, name):
    with Session(engine) as db:
        if db.scalar(text("SELECT version_num FROM alembic_version")) != SCHEMA_HEAD:
            raise ValueError(
                "Deploy the current Render API successfully before creating an account."
            )
        return manage_user(db, email, password, name)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    engine = None
    try:
        value = validate_url(getpass.getpass("Direct Neon connection URL (hidden): ").strip())
        email = input("Your CareerOS email: ").strip()
        name = input("Your name: ").strip()
        password = getpass.getpass("New CareerOS password (12+ characters, hidden): ")
        if password != getpass.getpass("Confirm password (hidden): "):
            raise ValueError("Passwords did not match; nothing changed.")
        engine = build_engine(value)
        create_account(engine, email, password, name)
        print("Cloud account created without demo data. Sign in at your Netlify production URL.")
        print("Your local database and environment files were not changed.")
    except (ValueError, SQLAlchemyError):
        # Database/provider errors and validation details can contain secrets: do not echo them.
        print(
            "Account was not created. Check the direct TLS URL, deployed schema, email and password requirements. An existing account is never overwritten."
        )
        raise SystemExit(1) from None
    except (KeyboardInterrupt, EOFError):
        print("Account setup cancelled.")
        raise SystemExit(1) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
