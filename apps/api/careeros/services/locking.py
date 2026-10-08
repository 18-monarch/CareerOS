"""Session-scoped advisory lock; local fallback uses an OS lock for the SQLite dev DB."""

import errno
import hashlib
import os
import tempfile
from contextlib import contextmanager

from sqlalchemy import text


def _file_lock(file, *, release=False):
    if os.name == "nt":
        import msvcrt

        # Windows byte-range locks can extend beyond EOF; no write/truncate is needed.
        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK if release else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(file, fcntl.LOCK_UN if release else fcntl.LOCK_EX | fcntl.LOCK_NB)


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
        # Include database identity so independent local databases do not block each other.
        database = hashlib.sha256(str(engine.url).encode()).hexdigest()[:12]
        path = os.path.join(tempfile.gettempdir(), f"careeros-{database}-{number}.lock")
        with open(path, "a+b") as file:
            try:
                _file_lock(file)
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                yield False
                return
            try:
                yield True
            finally:
                _file_lock(file, release=True)
