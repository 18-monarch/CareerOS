import asyncio

from careeros.db import get_db
from careeros.models import AuditLog, Occurrence, Source, User
from careeros.routers.profile import owned
from careeros.schemas import SourceIn
from careeros.security import current_user, job_writer, rate_limit
from careeros.services.ingestion import health_summary, ingest_source
from careeros.services.locking import job_lock
from careeros.services.notifications import generate
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Sources and processing"])


@router.get("/sources")
@router.get("/sources/health")
def sources(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return health_summary(db, list(db.scalars(select(Source).where(Source.user_id == user.id))))


@router.post("/sources", status_code=201)
def add_source(body: SourceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = Source(
        user_id=user.id,
        name=body.name,
        kind=body.kind,
        enabled=body.enabled,
        config=body.model_dump(exclude={"name", "kind", "enabled"}),
    )
    db.add(row)
    db.commit()
    return {"id": row.id, **body.model_dump()}


@router.put("/sources/{id}")
def edit_source(
    id: str, body: SourceIn, user: User = Depends(job_writer), db: Session = Depends(get_db)
):
    row = owned(db, Source, id, user)
    imported = db.scalar(select(Occurrence.id).where(Occurrence.source_id == id).limit(1))
    identity_changed = body.kind != row.kind or any(
        getattr(body, k) != row.config.get(k, "" if k == "board" else None)
        for k in ("board", "feed_url")
    )
    if imported and identity_changed:
        raise HTTPException(
            409,
            "This source already has imported records. Add a new source to change its board, feed URL or adapter; existing provenance is retained.",
        )
    row.name, row.kind, row.enabled = body.name, body.kind, body.enabled
    row.config = body.model_dump(exclude={"name", "kind", "enabled"})
    db.add(AuditLog(user_id=user.id, action="source.updated", target_id=row.id))
    db.commit()
    return {"id": row.id, **body.model_dump()}


@router.patch("/sources/{id}/toggle")
def toggle(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned(db, Source, id, user)
    row.enabled = not row.enabled
    db.commit()
    return {"enabled": row.enabled}


@router.post("/sources/{id}/ingest")
def ingest(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned(db, Source, id, user)
    rate_limit(db, f"ingest:{user.id}", 20, 3600)
    # Sync SQLAlchemy work stays in FastAPI's thread pool; external I/O is async within this task.
    result = asyncio.run(ingest_source(db, row))
    with job_lock(db.bind, f"notify:{user.id}") as acquired:
        if acquired:
            generate(db, user, "high-match")
    return result


@router.post("/notifications/generate")
def notifications_generate(user: User = Depends(current_user), db: Session = Depends(get_db)):
    with job_lock(db.bind, f"notify:{user.id}") as acquired:
        if not acquired:
            return {"created": 0, "status": "already running"}
        return {
            "created": sum(generate(db, user, kind) for kind in ("high-match", "deadline", "daily"))
        }
