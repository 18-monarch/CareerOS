"""Application preparation uses stored facts. Submission is a separate local browser process."""

import hashlib
import json

from careeros.db import utcnow
from careeros.models import Application, ApplicationDraft, Job, ResumeVersion
from careeros.schemas import ApplicationSettingsIn
from careeros.services.matching import match
from careeros.services.repository import candidate_context, serialize_job
from fastapi import HTTPException
from sqlalchemy import select

TERMINAL = {"SUBMITTED", "SUBMITTING", "UNCERTAIN"}


def settings_for(db, user):
    return ApplicationSettingsIn(
        **candidate_context(db, user)[3].get("application_settings", {})
    ).model_dump()


def fingerprint(db, user, job, resume):
    p, s, projects, _ = candidate_context(db, user)
    posting = serialize_job(job)
    # Exclude polling timestamps; include all material posting, profile, resume and policy facts.
    material = {
        k: posting.get(k)
        for k in (
            "title",
            "description",
            "application_url",
            "requirements",
            "provenance",
            "is_active",
            "country",
            "application_deadline",
            "required_skills",
            "preferred_skills",
        )
    }
    payload = {
        "profile": p,
        "skills": s,
        "projects": projects,
        "job": material,
        "resume": {"id": resume.id, "data": resume.data} if resume else None,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def already_applied(db, user_id, job_id):
    app = db.scalar(
        select(Application).where(Application.user_id == user_id, Application.job_id == job_id)
    )
    return app and (
        app.applied_at or app.status not in ("SAVED", "DISCOVERED", "PLANNING_TO_APPLY")
    )


def prepare(db, user, job):
    draft = db.scalar(
        select(ApplicationDraft).where(
            ApplicationDraft.user_id == user.id, ApplicationDraft.job_id == job.id
        )
    )
    if draft and draft.status in TERMINAL:
        raise HTTPException(
            409,
            "Submission already recorded or uncertain. Check the existing attempt; do not retry blindly.",
        )
    if job.is_demo or not job.is_active or not job.application_url:
        raise HTTPException(422, "Choose a live opportunity with an application link")
    if already_applied(db, user.id, job.id):
        raise HTTPException(409, "This opportunity is already marked applied or beyond")
    profile, skills, projects, prefs = candidate_context(db, user)
    posting = serialize_job(job)
    matched = match(profile, posting, skills, projects, prefs)
    settings = settings_for(db, user)
    design = "design" in posting["categories"]
    resume_id = settings["design_resume_id" if design else "software_resume_id"]
    resume = db.get(ResumeVersion, resume_id) if resume_id else None
    if resume and resume.user_id != user.id:
        raise HTTPException(422, "Resume does not belong to this account")
    skills_text = ", ".join(matched["strong_matches"][:6])
    related = [
        p
        for p in projects
        if set(map(str.casefold, p.get("verified_skills", []))) & set(matched["strong_matches"])
    ]
    letter = (
        f"Hello {job.company.name} hiring team,\n\nI am interested in the {job.title} opportunity."
    )
    if profile.get("degree") and profile.get("university"):
        letter += f" I am studying {profile['degree']} at {profile['university']}."
    if profile.get("graduation_year"):
        letter += f" My expected graduation year is {profile['graduation_year']}."
    if skills_text:
        letter += f" My relevant skills include {skills_text}."
    if related:
        letter += (
            " I would welcome the opportunity to discuss my work on "
            + ", ".join(p["name"] for p in related[:2])
            + "."
        )
    letter += f"\n\nThank you for considering my application.\n{user.name}"
    blockers = []
    if not resume or not resume.data.get("sha256"):
        blockers.append("Upload a PDF and select a resume for this career track.")
    portfolio = next(
        (
            v
            for k, v in profile["external_profiles"].items()
            if k.casefold() in ("portfolio", "behance", "dribbble")
        ),
        "",
    )
    if design and not portfolio:
        blockers.append("Add a portfolio link to My profile for design applications.")
    if matched["eligibility"]["state"] in ("NOT_ELIGIBLE", "CLOSED"):
        blockers.append("The current eligibility assessment blocks this application.")
    packet = {
        "name": user.name,
        "email": user.email,
        "phone": settings["phone"],
        "links": profile["external_profiles"],
        "cover_letter": letter,
        "answers": settings["answers"],
        "resume_id": resume_id,
        "resume_name": resume.name if resume else None,
        "resume_sha256": resume.data.get("sha256") if resume else None,
    }
    data = {
        "company": job.company.name,
        "title": job.title,
        "url": job.application_url,
        "categories": posting["categories"],
        "country": job.country,
        "score": matched["score"],
        "eligibility": matched["eligibility"],
        "packet": packet,
        "blockers": blockers,
        "fingerprint": fingerprint(db, user, job, resume),
        "prepared_at": utcnow().isoformat(),
        "supported": supported_url(job.application_url),
    }
    if not draft:
        draft = ApplicationDraft(user_id=user.id, job_id=job.id)
        db.add(draft)
    draft.status, draft.data = "DRAFT", data
    db.commit()
    return draft


def supported_url(url):
    from careeros.services.research import ats_reference

    ref = ats_reference(url)
    return bool(ref and ref[0] == "lever")


def current_blockers(db, user, draft):
    blockers = list(draft.data.get("blockers", []))
    job = db.get(Job, draft.job_id)
    resume = (
        db.get(ResumeVersion, draft.data["packet"]["resume_id"])
        if draft.data["packet"]["resume_id"]
        else None
    )
    if not job.is_active or (job.application_deadline and job.application_deadline <= utcnow()):
        blockers.append("Posting is inactive or its recorded deadline passed.")
    if fingerprint(db, user, job, resume) != draft.data["fingerprint"]:
        blockers.append(
            "Profile, posting, resume or settings changed. Prepare a new draft and review it."
        )
    if already_applied(db, user.id, job.id):
        blockers.append("Application already exists beyond the preparation stage.")
    return blockers


def approve(db, user, draft, reviewed):
    if draft.status != "DRAFT":
        raise HTTPException(409, "Only a draft can be approved; prepare again if appropriate")
    if not reviewed:
        raise HTTPException(422, "Review the packet and confirm eligibility and availability first")
    blockers = current_blockers(db, user, draft)
    if blockers:
        raise HTTPException(422, " ".join(blockers))
    draft.status = "APPROVED"
    draft.data = {
        **draft.data,
        "approved_at": utcnow().isoformat(),
        "approval": "individual_review",
    }
    db.commit()
    return draft


def auto_prepare(db, user):
    from careeros.services.repository import ranked_jobs

    cfg = settings_for(db, user)
    if not cfg["auto_prepare"]:
        return 0
    existing = set(
        db.scalars(select(ApplicationDraft.job_id).where(ApplicationDraft.user_id == user.id))
    )
    count = 0
    for item in ranked_jobs(db, user):
        if count >= cfg["daily_limit"]:
            break
        if (
            item["id"] in existing
            or item["is_demo"]
            or not item["is_active"]
            or item["match"]["score"] < cfg["minimum_score"]
            or item["country"] not in cfg["countries"]
        ):
            continue
        if item["match"]["eligibility"]["state"] in ("CLOSED", "NOT_ELIGIBLE"):
            continue
        try:
            prepare(db, user, db.get(Job, item["id"]))
            count += 1
        except HTTPException:
            continue
    return count


def can_auto_approve(db, user, draft):
    cfg = settings_for(db, user)
    # Auto submission only after human review of posting requirements, including availability.
    job = db.get(Job, draft.job_id)
    return bool(
        cfg["mode"] == "auto_submit"
        and job.data.get("human_reviewed")
        and draft.data["company"].casefold() in [c.casefold() for c in cfg["companies"]]
        and draft.data["country"] in cfg["countries"]
        and draft.data["score"] >= cfg["minimum_score"]
        and draft.data["eligibility"]["state"] == "ELIGIBLE"
        and draft.data["supported"]
        and not current_blockers(db, user, draft)
    )
