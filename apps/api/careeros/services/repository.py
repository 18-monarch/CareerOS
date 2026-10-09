import hashlib
import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from careeros.db import utcnow
from careeros.models import (
    Company,
    Job,
    JobRequirement,
    JobSkill,
    Occurrence,
    Preferences,
    Profile,
    Project,
    Skill,
    Source,
    UserSkill,
)
from careeros.schemas import PreferenceIn
from careeros.services.matching import match, skill_key
from sqlalchemy import select


def shared_record(db, model, key, value, **fields):
    """The unique constraint arbitrates cross-user races without aborting ingestion."""
    record = db.scalar(select(model).where(getattr(model, key) == value))
    if record:
        return record
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(
        insert(model)
        .values(**{key: value}, **fields)
        .on_conflict_do_nothing(index_elements=[getattr(model, key)])
    )
    return db.scalar(select(model).where(getattr(model, key) == value))


def company_record(db, name, domain=None):
    return shared_record(
        db, Company, "normalized_name", normalized_text(name), name=name, domain=domain
    )


def normalized_text(text):
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def normalized_url(url):
    if not url:
        return ""
    u = urlsplit(url)
    query = urlencode(
        sorted(
            (k, v)
            for k, v in parse_qsl(u.query)
            if not k.startswith("utm_") and k not in ("ref", "source")
        )
    )
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path.rstrip("/"), query, ""))


def identity(data):
    company = normalized_text(data["company_name"])
    if data.get("requisition_id"):
        key = f"{company}|req|{data['requisition_id']}"
    elif data.get("application_url"):
        key = f"{company}|url|{normalized_url(data['application_url'])}"
    else:
        key = f"{company}|{normalized_text(data['title'])}|{data.get('country')}|{','.join(sorted(normalized_text(x) for x in data.get('locations', [])))}|{data.get('employment_type')}"
    return hashlib.sha256(key.encode()).hexdigest()


def skill_record(db, name, category="Programming"):
    key = skill_key(name)
    return shared_record(db, Skill, "name", key, category=category)


def profile_data(db, user):
    p = db.scalar(select(Profile).where(Profile.user_id == user.id))
    pref = db.scalar(select(Preferences).where(Preferences.user_id == user.id))
    fields = [
        "university",
        "degree",
        "branch",
        "graduation_year",
        "cgpa",
        "semester",
        "experience_years",
        "work_authorizations",
        "external_profiles",
    ]
    return {
        "name": user.name,
        "email": user.email,
        **{k: getattr(p, k) for k in fields},
        "preferences": {**PreferenceIn().model_dump(), **(pref.data if pref else {})},
    }


def candidate_context(db, user):
    profile = profile_data(db, user)
    skills = [
        {"id": s.id, "name": s.skill.name, "category": s.skill.category, **s.data}
        for s in db.scalars(select(UserSkill).where(UserSkill.user_id == user.id))
    ]
    projects = [
        {"id": p.id, "name": p.name, **p.data}
        for p in db.scalars(select(Project).where(Project.user_id == user.id))
    ]
    return profile, skills, projects, profile["preferences"]


def serialize_job(job):
    from careeros.services.categories import classify

    fields = [
        "id",
        "title",
        "normalized_role",
        "description",
        "employment_type",
        "country",
        "locations",
        "remote_status",
        "application_url",
        "source_url",
        "source",
        "external_id",
        "application_deadline",
        "posted_at",
        "expires_at",
        "is_active",
        "is_demo",
        "last_seen_at",
        "created_at",
        "updated_at",
    ]
    return {
        **{k: getattr(job, k) for k in fields},
        "company_name": job.company.name,
        "company_domain": job.company.domain,
        "requirements": job.requirements.data,
        "provenance": job.requirements.provenance,
        "required_skills": [s.skill.name for s in job.skills if s.required],
        "preferred_skills": [s.skill.name for s in job.skills if not s.required],
        **job.data,
        "categories": classify(job.title),
    }


def ranked_jobs(db, user):
    context = candidate_context(db, user)
    jobs = [
        serialize_job(job) for job in db.scalars(select(Job).where(Job.user_id == user.id)).unique()
    ]
    for job in jobs:
        job["match"] = match(context[0], job, context[1], context[2], context[3])
    return sorted(
        jobs,
        key=lambda j: (
            -j["match"]["score"],
            j["application_deadline"] or __import__("datetime").datetime.max,
            j["id"],
        ),
    )


def manual_source(db, user_id, kind):
    source = db.scalar(
        select(Source).where(
            Source.user_id == user_id, Source.kind == kind, Source.name == kind.capitalize()
        )
    )
    if not source:
        source = Source(user_id=user_id, kind=kind, name=kind.capitalize(), config={})
        db.add(source)
        db.flush()
    return source


def upsert_job(db, user_id, input_job, source, raw=None):
    data = input_job.model_dump(mode="json")
    canonical = identity(data)
    external = input_job.external_id or canonical
    occurrence = db.scalar(
        select(Occurrence).where(
            Occurrence.source_id == source.id, Occurrence.external_id == external
        )
    )
    job = (
        db.get(Job, occurrence.job_id)
        if occurrence
        else db.scalar(select(Job).where(Job.user_id == user_id, Job.canonical_key == canonical))
    )
    company = company_record(db, input_job.company_name, input_job.company_domain)
    # Conservative cross-source fuzzy fallback: same company, location, type, no conflicting requisition IDs.
    if not job:
        for candidate in db.scalars(
            select(Job).where(
                Job.user_id == user_id,
                Job.company_id == company.id,
                Job.country == input_job.country,
                Job.employment_type == input_job.employment_type,
            )
        ).unique():
            old_req, new_req = candidate.data.get("requisition_id"), input_job.requisition_id
            if old_req and new_req and old_req != new_req:
                continue
            same_url = input_job.application_url and normalized_url(
                input_job.application_url
            ) == normalized_url(candidate.application_url)
            fuzzy = (
                not (old_req or new_req)
                and not (
                    candidate.external_id
                    and input_job.external_id
                    and candidate.source == input_job.source
                    and candidate.external_id != input_job.external_id
                )
                and sorted(map(normalized_text, candidate.locations))
                == sorted(map(normalized_text, input_job.locations))
                and SequenceMatcher(
                    None, normalized_text(candidate.title), normalized_text(input_job.title)
                ).ratio()
                >= 0.96
            )
            if same_url or fuzzy:
                job = candidate
                break
    created = job is None
    if created:
        job = Job(user_id=user_id, company_id=company.id, canonical_key=canonical)
        db.add(job)
    metadata = job.data or {}
    primary_source = metadata.get("primary_source_id")
    if not created and not primary_source:
        primary_source = db.scalar(
            select(Occurrence.source_id)
            .where(Occurrence.job_id == job.id)
            .order_by(Occurrence.created_at, Occurrence.id)
            .limit(1)
        )
    fields = [
        "title",
        "normalized_role",
        "description",
        "employment_type",
        "country",
        "locations",
        "remote_status",
        "application_url",
        "source_url",
        "source",
        "external_id",
        "application_deadline",
        "posted_at",
        "expires_at",
        "is_active",
        "is_demo",
    ]
    # An existing canonical record is updated only by its primary source; secondary copies add provenance.
    if (
        created
        or (occurrence and primary_source == source.id and not metadata.get("human_reviewed"))
        or input_job.source in ("manual", "campus")
    ):
        for key in fields:
            setattr(job, key, getattr(input_job, key))
        job.data = {
            **metadata,
            "primary_source_id": primary_source or source.id,
            **{
                k: data[k]
                for k in (
                    "requisition_id",
                    "salary_min",
                    "salary_max",
                    "salary_currency",
                    "salary_period",
                    "stipend",
                    "selection_stages",
                )
            },
        }
        if created:
            job.requirements = JobRequirement(
                data=data["requirements"], provenance=input_job.provenance
            )
        else:
            job.requirements.data, job.requirements.provenance = (
                data["requirements"],
                input_job.provenance,
            )
        job.skills.clear()
        db.flush()
        required = {skill_key(x) for x in input_job.required_skills}
        preferred = {skill_key(x) for x in input_job.preferred_skills} - required
        for name in sorted(required | preferred):
            job.skills.append(
                JobSkill(skill_id=skill_record(db, name).id, required=name in required)
            )
    if metadata.get("manually_archived"):
        job.is_active = False
    elif metadata.get("source_closed") and input_job.is_active:
        job.is_active = True
        job.data = {**job.data, "source_closed": False}
    job.last_seen_at = utcnow()
    db.flush()
    if not occurrence:
        occurrence = Occurrence(source_id=source.id, job_id=job.id, external_id=external)
        db.add(occurrence)
    occurrence.source_url = input_job.source_url
    occurrence.raw_payload = raw if raw is not None else data
    occurrence.last_seen_at = utcnow()
    occurrence.is_active = input_job.is_active
    occurrence.missing_runs = 0
    db.flush()
    return job, created
