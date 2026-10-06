from careeros.db import get_db
from careeros.models import Source, User
from careeros.routers.profile import owned
from careeros.schemas import SourceIn
from careeros.security import current_user, rate_limit
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
    if body.kind in ("greenhouse", "lever", "ashby") and not body.board:
        raise HTTPException(422, "Board token required")
    if body.kind == "official" and not body.feed_url:
        raise HTTPException(422, "Approved feed URL required")
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


@router.patch("/sources/{id}/toggle")
def toggle(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned(db, Source, id, user)
    row.enabled = not row.enabled
    db.commit()
    return {"enabled": row.enabled}


@router.post("/sources/{id}/ingest")
async def ingest(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = owned(db, Source, id, user)
    rate_limit(db, f"ingest:{user.id}", 20, 3600)
    result = await ingest_source(db, row)
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
