from careeros.db import get_db, utcnow
from careeros.models import Application, ApplicationEvent, AuditLog, Job, ResumeVersion, User
from careeros.routers.profile import owned
from careeros.schemas import ApplicationIn
from careeros.security import current_user
from careeros.services.analytics import funnel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/applications", tags=["Applications"])


def serialize(app):
    return {
        "id": app.id,
        "job_id": app.job_id,
        "title": app.job.title,
        "company_name": app.job.company.name,
        "deadline": app.job.application_deadline,
        "is_demo": app.job.is_demo,
        "status": app.status,
        "applied_at": app.applied_at,
        "created_at": app.created_at,
        **app.data,
        "events": [
            {"id": e.id, "status": e.status, "note": e.note, "created_at": e.created_at}
            for e in app.events
        ],
    }


@router.get("")
def applications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        serialize(a)
        for a in db.scalars(
            select(Application)
            .where(Application.user_id == user.id)
            .order_by(Application.updated_at.desc())
        ).unique()
    ]


@router.get("/metrics")
def metrics(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return funnel(
        list(db.scalars(select(Application).where(Application.user_id == user.id)).unique())
    )


def write_application(db, user, body, app=None):
    owned(db, Job, body.job_id, user)
    if body.resume_id:
        owned(db, ResumeVersion, body.resume_id, user)
    if app and app.job_id != body.job_id:
        raise HTTPException(422, "Cannot change application job")
    if not app:
        app = Application(user_id=user.id, job_id=body.job_id, status=body.status, data={})
        db.add(app)
        db.flush()
        changed = True
    else:
        changed = app.status != body.status
    if changed or app.data.get("notes") != body.notes:
        app.events.append(ApplicationEvent(status=body.status, note=body.notes))
    app.status = body.status
    if (
        body.status
        in ("APPLIED", "OA_RECEIVED", "OA_COMPLETED", "INTERVIEW", "FINAL_ROUND", "OFFER")
        and not app.applied_at
    ):
        app.applied_at = utcnow()
    app.data = {**app.data, **body.model_dump(mode="json", exclude={"job_id", "status"})}
    db.add(AuditLog(user_id=user.id, action="application.updated", target_id=app.id))
    db.commit()
    return serialize(app)


@router.post("", status_code=201)
def add_application(
    body: ApplicationIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    existing = db.scalar(
        select(Application).where(Application.user_id == user.id, Application.job_id == body.job_id)
    )
    if existing:
        raise HTTPException(409, "Application already exists; update its status")
    return write_application(db, user, body)


@router.patch("/{id}")
def edit_application(
    id: str, body: ApplicationIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    app = db.scalar(
        select(Application)
        .where(Application.id == id, Application.user_id == user.id)
        .with_for_update(of=Application)
    )
    if not app:
        raise HTTPException(404, "Record not found")
    return write_application(db, user, body, app)


@router.get("/{id}/events")
def history(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return serialize(owned(db, Application, id, user))["events"]
