from careeros.db import get_db
from careeros.models import (
    AuditLog,
    Preferences,
    Profile,
    Project,
    ProjectMastery,
    ResumeVersion,
    User,
    UserSkill,
)
from careeros.schemas import MasteryIn, ProfileIn, ProjectIn, ResumeIn, SkillIn
from careeros.security import current_user
from careeros.services.repository import candidate_context, profile_data, skill_record
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Career profile"])


def owned(db, model, id, user):
    row = db.get(model, id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Record not found")
    return row


@router.get("/profile")
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return profile_data(db, user)


@router.put("/profile")
def update_profile(
    body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
    pref = db.scalar(select(Preferences).where(Preferences.user_id == user.id))
    for key, value in body.model_dump(exclude={"name", "preferences"}).items():
        setattr(profile, key, value)
    user.name, pref.data = body.name, body.preferences.model_dump()
    db.add(AuditLog(user_id=user.id, action="profile.updated", target_id=profile.id))
    db.commit()
    return profile_data(db, user)


@router.get("/skills")
def skills(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return candidate_context(db, user)[1]


@router.post("/skills", status_code=201)
def add_skill(body: SkillIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    skill = skill_record(db, body.name, body.category)
    row = db.scalar(
        select(UserSkill).where(UserSkill.user_id == user.id, UserSkill.skill_id == skill.id)
    )
    if not row:
        row = UserSkill(user_id=user.id, skill_id=skill.id)
        db.add(row)
    row.data = body.model_dump(exclude={"name"})
    db.commit()
    return {"id": row.id, **body.model_dump()}


@router.delete("/skills/{id}")
def remove_skill(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned(db, UserSkill, id, user))
    db.commit()
    return {"ok": True}


@router.get("/projects")
def projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    records = list(db.scalars(select(Project).where(Project.user_id == user.id)))
    mastery = (
        list(
            db.scalars(
                select(ProjectMastery).where(ProjectMastery.project_id.in_([p.id for p in records]))
            )
        )
        if records
        else []
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            **p.data,
            "mastery": [
                {"id": m.id, "topic": m.topic, **m.data} for m in mastery if m.project_id == p.id
            ],
        }
        for p in records
    ]


@router.post("/projects", status_code=201)
def add_project(body: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = Project(user_id=user.id, name=body.name, data=body.model_dump(exclude={"name"}))
    db.add(p)
    db.commit()
    return {"id": p.id, "name": p.name, **p.data}


@router.put("/projects/{id}")
def edit_project(
    id: str, body: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    p = owned(db, Project, id, user)
    p.name, p.data = body.name, body.model_dump(exclude={"name"})
    db.commit()
    return {"id": p.id, "name": p.name, **p.data}


@router.delete("/projects/{id}")
def delete_project(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned(db, Project, id, user))
    db.commit()
    return {"ok": True}


@router.put("/projects/{id}/mastery")
def edit_mastery(
    id: str, body: MasteryIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    owned(db, Project, id, user)
    row = db.scalar(
        select(ProjectMastery).where(
            ProjectMastery.project_id == id, ProjectMastery.topic == body.topic
        )
    )
    if not row:
        row = ProjectMastery(project_id=id, topic=body.topic)
        db.add(row)
    row.data = body.model_dump(exclude={"topic"})
    db.commit()
    return {"id": row.id, "topic": row.topic, **row.data}


@router.get("/resumes")
def resumes(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        {"id": r.id, "name": r.name, **r.data}
        for r in db.scalars(select(ResumeVersion).where(ResumeVersion.user_id == user.id))
    ]


@router.post("/resumes", status_code=201)
def add_resume(body: ResumeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    if body.is_master:
        for row in db.scalars(select(ResumeVersion).where(ResumeVersion.user_id == user.id)):
            row.data = {**row.data, "is_master": False}
    row = ResumeVersion(user_id=user.id, name=body.name, data=body.model_dump(exclude={"name"}))
    db.add(row)
    db.commit()
    return {"id": row.id, "name": row.name, **row.data}


@router.put("/resumes/{id}")
def edit_resume(
    id: str, body: ResumeIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    row = owned(db, ResumeVersion, id, user)
    if body.is_master:
        for other in db.scalars(select(ResumeVersion).where(ResumeVersion.user_id == user.id)):
            other.data = {**other.data, "is_master": False}
    row.name, row.data = body.name, body.model_dump(exclude={"name"})
    db.commit()
    return {"id": row.id, "name": row.name, **row.data}


@router.delete("/resumes/{id}")
def delete_resume(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from careeros.models import Application

    for application in db.scalars(
        select(Application).where(Application.user_id == user.id)
    ).unique():
        if application.data.get("resume_id") == id:
            raise HTTPException(
                409,
                "This resume is linked to an application. Keep it for your records, or unlink it first.",
            )
    db.delete(owned(db, ResumeVersion, id, user))
    db.commit()
    return {"ok": True}
