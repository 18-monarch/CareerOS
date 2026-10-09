import base64
import binascii
import hashlib

from careeros.db import get_db, utcnow
from careeros.models import ApplicationDraft, Job, Preferences, ResumeVersion, User
from careeros.routers.profile import owned
from careeros.schemas import ApplicationSettingsIn, Schema
from careeros.security import current_user, rate_limit
from careeros.services.application_desk import approve, prepare, settings_for
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Application desk"])


class PDFIn(Schema):
    content_base64: str = Field(max_length=900000)


class PrepareIn(Schema):
    job_id: str


class ApprovalIn(Schema):
    reviewed: bool


class DraftEdit(Schema):
    @field_validator("answers")
    @classmethod
    def validate_answers(cls, value):
        return ApplicationSettingsIn.bounded_answers(value)

    cover_letter: str = Field(max_length=10000)
    answers: dict[str, str] = Field(default_factory=dict, max_length=40)


def serialize(row):
    return {"id": row.id, "job_id": row.job_id, "status": row.status, **row.data}


@router.get("/application-desk")
def desk(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = list(
        db.scalars(
            select(ApplicationDraft)
            .where(ApplicationDraft.user_id == user.id)
            .order_by(ApplicationDraft.updated_at.desc())
        )
    )
    return {
        "settings": settings_for(db, user),
        "drafts": [serialize(r) for r in rows],
        "supported_sites": ["jobs.lever.co"],
        "runner_required": True,
    }


@router.put("/application-settings")
def update_settings(
    body: ApplicationSettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    for resume_id in (body.software_resume_id, body.design_resume_id):
        if resume_id:
            owned(db, ResumeVersion, resume_id, user)
    pref = db.scalar(select(Preferences).where(Preferences.user_id == user.id))
    pref.data = {**pref.data, "application_settings": body.model_dump()}
    db.commit()
    return body.model_dump()


@router.put("/resumes/{id}/pdf")
def upload_pdf(
    id: str, body: PDFIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    resume = owned(db, ResumeVersion, id, user)
    try:
        content = base64.b64decode(body.content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(422, "Invalid PDF encoding") from exc
    if not content.startswith(b"%PDF-") or len(content) > 650000 or b"%%EOF" not in content[-1024:]:
        raise HTTPException(422, "Choose a PDF no larger than 650 KB")
    resume.data = {
        **resume.data,
        "content_base64": body.content_base64,
        "sha256": hashlib.sha256(content).hexdigest(),
        "uploaded_at": utcnow().isoformat(),
    }
    db.commit()
    return {"sha256": resume.data["sha256"], "size": len(content)}


@router.post("/application-desk/prepare", status_code=201)
def prepare_draft(
    body: PrepareIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    rate_limit(db, f"prepare:{user.id}", 30, 3600)
    return serialize(prepare(db, user, owned(db, Job, body.job_id, user)))


@router.put("/application-desk/{id}")
def edit_draft(
    id: str, body: DraftEdit, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    draft = owned(db, ApplicationDraft, id, user)
    if draft.status != "DRAFT":
        raise HTTPException(409, "Only unapproved drafts can be edited")
    draft.data = {**draft.data, "packet": {**draft.data["packet"], **body.model_dump()}}
    db.commit()
    return serialize(draft)


@router.post("/application-desk/{id}/approve")
def approve_draft(
    id: str, body: ApprovalIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return serialize(approve(db, user, owned(db, ApplicationDraft, id, user), body.reviewed))


@router.post("/application-desk/{id}/cancel")
def cancel_draft(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    draft = owned(db, ApplicationDraft, id, user)
    if draft.status in ("SUBMITTING", "SUBMITTED", "UNCERTAIN"):
        raise HTTPException(
            409, "Submission is already in progress or needs confirmation; check its outcome first"
        )
    draft.status = "CANCELLED"
    db.commit()
    return serialize(draft)
