import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from careeros.config import get_settings
from careeros.db import get_db, utcnow
from careeros.models import AuthSession, RateBucket, User

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = hasher.hash("constant timing placeholder password")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def rate_limit(db, key, limit=10, seconds=900):
    key = digest(key)
    now = utcnow()
    # Atomic upsert prevents concurrent login attempts bypassing the count.
    from sqlalchemy import case
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    stmt = insert(RateBucket).values(key=key, count=1, window_start=now)
    expired = RateBucket.window_start < now - timedelta(seconds=seconds)
    stmt = stmt.on_conflict_do_update(
        index_elements=[RateBucket.key],
        set_={
            "count": case((expired, 1), else_=RateBucket.count + 1),
            "window_start": case((expired, now), else_=RateBucket.window_start),
        },
    ).returning(RateBucket.count)
    count = db.scalar(stmt)
    db.commit()
    if count > limit:
        raise HTTPException(
            429, "Too many attempts. Try again later.", headers={"Retry-After": str(seconds)}
        )


def set_tokens(db, response: Response, user_id, session=None):
    access, refresh, csrf = (secrets.token_urlsafe(32) for _ in range(3))
    if session is None:
        session = AuthSession(user_id=user_id)
        db.add(session)
    session.access_hash, session.refresh_hash, session.csrf_hash = map(
        digest, (access, refresh, csrf)
    )
    session.access_expires = utcnow() + timedelta(minutes=15)
    session.expires = utcnow() + timedelta(days=7)
    db.commit()
    for name, value, age, http_only in [
        ("career_access", access, 900, True),
        ("career_refresh", refresh, 604800, True),
        ("career_csrf", csrf, 604800, False),
    ]:
        response.set_cookie(
            name,
            value,
            max_age=age,
            httponly=http_only,
            secure=get_settings().cookie_secure,
            samesite="lax",
            path="/",
        )
    return {"csrf_token": csrf, "expires_in": 900}


def verify_csrf(request, session=None):
    origin = request.headers.get("origin")
    if origin and origin != get_settings().frontend_origin:
        raise HTTPException(403, "Origin not allowed")
    cookie, header = request.cookies.get("career_csrf", ""), request.headers.get("x-csrf-token", "")
    if not cookie or not secrets.compare_digest(cookie, header):
        raise HTTPException(403, "CSRF token missing or invalid")
    if session and not secrets.compare_digest(session.csrf_hash, digest(header)):
        raise HTTPException(403, "CSRF session mismatch")


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("career_access", "")
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.access_hash == digest(token),
            AuthSession.access_expires > utcnow(),
            AuthSession.expires > utcnow(),
        )
    )
    if not session:
        raise HTTPException(401, "Authentication required")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        verify_csrf(request, session)
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Authentication required")
    return user


def job_writer(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Manual edits and ingestion use the same per-user canonical-job lock."""
    from careeros.services.locking import job_lock

    with job_lock(db.bind, f"ingest-user:{user.id}") as acquired:
        if not acquired:
            raise HTTPException(409, "Job processing is running. Wait for it to finish and retry.")
        yield user
