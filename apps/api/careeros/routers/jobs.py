from datetime import UTC, datetime

from careeros.db import get_db
from careeros.models import Application, Job, Occurrence, User
from careeros.routers.profile import owned
from careeros.schemas import JobIn, NoticeIn
from careeros.security import current_user, job_writer, rate_limit
from careeros.services.ai import provider
from careeros.services.matching import match, skill_key
from careeros.services.repository import (
    candidate_context,
    company_record,
    manual_source,
    ranked_jobs,
    serialize_job,
    upsert_job,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Opportunities"])


@router.get("/jobs")
def jobs(
    q: str = "",
    role: str = "",
    company: str = "",
    category: str = "",
    country: str = "",
    city: str = "",
    remote: str = "",
    employment_type: str = "",
    eligibility: str = "",
    source: str = "",
    skill: str = "",
    state: str = "",
    min_score: int = Query(0, ge=0, le=100),
    graduation_year: int | None = None,
    max_cgpa: float | None = None,
    deadline_before: datetime | None = None,
    sort: str = "match",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    records = ranked_jobs(db, user)
    applications = {
        a.job_id: {"id": a.id, "status": a.status}
        for a in db.scalars(select(Application).where(Application.user_id == user.id)).unique()
    }
    result = []
    for j in records:
        j["application"] = applications.get(j["id"])
        if category and category not in j["categories"]:
            continue
        r = j["requirements"]
        if q.casefold() not in f"{j['title']} {j['company_name']} {j['description']}".casefold():
            continue
        if any(
            value and value.casefold() not in str(j[key]).casefold()
            for key, value in [
                ("normalized_role", role),
                ("company_name", company),
                ("country", country),
                ("locations", city),
            ]
        ):
            continue
        if any(
            value and j[key] != value
            for key, value in [
                ("remote_status", remote),
                ("employment_type", employment_type),
                ("source", source),
            ]
        ):
            continue
        if eligibility and j["match"]["eligibility"]["state"] != eligibility:
            continue
        if j["match"]["score"] < min_score or (
            skill and skill_key(skill) not in j["required_skills"] + j["preferred_skills"]
        ):
            continue
        if state and (not j["application"] or j["application"]["status"] != state):
            continue
        if graduation_year and (
            (
                r.get("allowed_graduation_years")
                and graduation_year not in r["allowed_graduation_years"]
            )
            or graduation_year < (r.get("graduation_year_min") or 0)
            or graduation_year > (r.get("graduation_year_max") or 9999)
        ):
            continue
        if (
            max_cgpa is not None
            and r.get("minimum_cgpa") is not None
            and r["minimum_cgpa"] > max_cgpa
        ):
            continue
        if deadline_before and (
            not j["application_deadline"]
            or j["application_deadline"]
            > (
                deadline_before.astimezone(UTC).replace(tzinfo=None)
                if deadline_before.tzinfo
                else deadline_before
            )
        ):
            continue
        result.append(j)
    if sort == "deadline":
        result.sort(key=lambda j: j["application_deadline"] or datetime.max)
    elif sort == "newest":
        result.sort(key=lambda j: j["created_at"], reverse=True)
    start = (page - 1) * page_size
    return {
        "items": result[start : start + page_size],
        "total": len(result),
        "page": page,
        "page_size": page_size,
    }


@router.post("/jobs", status_code=201)
def add_job(body: JobIn, user: User = Depends(job_writer), db: Session = Depends(get_db)):
    if body.source not in ("manual", "campus"):
        raise HTTPException(422, "Use manual or campus for user-created jobs")
    source = manual_source(db, user.id, body.source)
    job, created = upsert_job(db, user.id, body, source)
    db.commit()
    return {**serialize_job(job), "created": created}


@router.get("/jobs/{id}")
def job_detail(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = serialize_job(owned(db, Job, id, user))
    p, s, projects, pref = candidate_context(db, user)
    job["match"] = match(p, job, s, projects, pref)
    job["occurrences"] = [
        {
            "source_id": o.source_id,
            "external_id": o.external_id,
            "source_url": o.source_url,
            "first_seen_at": o.created_at,
            "last_seen_at": o.last_seen_at,
            "is_active": o.is_active,
            "missing_runs": o.missing_runs,
        }
        for o in db.scalars(select(Occurrence).where(Occurrence.job_id == id))
    ]
    app = db.scalar(
        select(Application).where(Application.user_id == user.id, Application.job_id == id)
    )
    job["application"] = {"id": app.id, "status": app.status} if app else None
    return job


@router.get("/jobs/{id}/eligibility")
def job_eligibility(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return job_detail(id, user, db)["match"]["eligibility"]


@router.get("/jobs/{id}/match")
def job_match(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return job_detail(id, user, db)["match"]


@router.patch("/jobs/{id}/archive")
def archive(id: str, user: User = Depends(job_writer), db: Session = Depends(get_db)):
    j = owned(db, Job, id, user)
    j.is_active = False
    j.data = {**j.data, "manually_archived": True}
    db.commit()
    return {"ok": True}


@router.patch("/jobs/{id}/restore")
def restore(id: str, user: User = Depends(job_writer), db: Session = Depends(get_db)):
    j = owned(db, Job, id, user)
    j.is_active = True
    j.data = {**j.data, "manually_archived": False, "source_closed": False}
    db.commit()
    return {"ok": True}


@router.post("/campus/parse")
async def campus_parse(
    body: NoticeIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    rate_limit(db, f"campus-parse:{user.id}", 20, 3600)
    return await provider().parse_job_description(body.text)


@router.post("/campus/jobs", status_code=201)
def campus_add(body: JobIn, user: User = Depends(job_writer), db: Session = Depends(get_db)):
    body.source = "campus"
    return add_job(body, user, db)


@router.get("/campus/jobs")
def campus_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [j for j in ranked_jobs(db, user) if j["source"] == "campus"]


@router.put("/jobs/{id}")
def edit_job(id: str, body: JobIn, user: User = Depends(job_writer), db: Session = Depends(get_db)):
    """Human correction retains original source occurrence payloads for audit."""
    from careeros.models import AuditLog, JobSkill
    from careeros.services.repository import identity, skill_record

    job = owned(db, Job, id, user)
    new_key = identity(
        {**body.model_dump(mode="json"), "requisition_id": job.data.get("requisition_id")}
    )
    conflict = db.scalar(
        select(Job).where(Job.user_id == user.id, Job.canonical_key == new_key, Job.id != id)
    )
    if conflict:
        raise HTTPException(409, "Another canonical job already has this identity")
    company = company_record(db, body.company_name, body.company_domain)
    job.company_id, job.canonical_key = company.id, new_key
    for key in [
        "title",
        "normalized_role",
        "description",
        "country",
        "locations",
        "employment_type",
        "remote_status",
        "application_url",
        "application_deadline",
    ]:
        setattr(job, key, getattr(body, key))
    job.requirements.data = body.requirements.model_dump(mode="json")
    job.requirements.provenance = body.provenance
    job.data = {
        **job.data,
        **body.model_dump(
            mode="json",
            include={
                "salary_min",
                "salary_max",
                "salary_currency",
                "salary_period",
                "stipend",
                "selection_stages",
            },
        ),
        "human_reviewed": True,
    }
    job.skills.clear()
    db.flush()
    required = {skill_key(s) for s in body.required_skills}
    preferred = {skill_key(s) for s in body.preferred_skills} - required
    for name in sorted(required | preferred):
        job.skills.append(JobSkill(skill_id=skill_record(db, name).id, required=name in required))
    db.add(AuditLog(user_id=user.id, action="job.reviewed", target_id=job.id))
    db.commit()
    db.expire(job)
    return serialize_job(job)
