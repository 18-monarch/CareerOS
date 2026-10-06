"""Session-scoped advisory lock; local fallback uses an OS lock for the SQLite dev DB."""

import hashlib
import os
import tempfile
from contextlib import contextmanager

from sqlalchemy import text


@contextmanager
def job_lock(engine, name):
    number = int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "big", signed=True)
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection:
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": number})
            try:
                yield bool(acquired)
            finally:
                if acquired:
                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": number})
    else:
        import fcntl

        # Include database identity so independent local databases do not block each other.
        database = hashlib.sha256(str(engine.url).encode()).hexdigest()[:12]
        path = os.path.join(tempfile.gettempdir(), f"careeros-{database}-{number}.lock")
        with open(path, "w") as file:
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(file, fcntl.LOCK_UN)
