"""Opt-in, idempotent demo fixture. Never runs automatically in production."""

import argparse
import os
from datetime import timedelta

from sqlalchemy import select

from careeros.db import SessionLocal, utcnow
from careeros.models import Preferences, Profile, Project, ProjectMastery, User, UserSkill
from careeros.schemas import JobIn, PreferenceIn
from careeros.security import hasher
from careeros.services.notifications import generate
from careeros.services.repository import manual_source, skill_record, upsert_job


def seed(db, email, password, today=None):
    existing = db.scalar(select(User).where(User.email == email.lower()))
    if existing:
        return existing, False
    # Fixed anchor can be supplied for reproducible tests; local demo deadlines stay useful on installation.
    anchor = today or utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    user = User(email=email.lower(), name="Mohit Chaudhari", password_hash=hasher.hash(password))
    db.add(user)
    db.flush()
    db.add(
        Profile(
            user_id=user.id,
            university="Nirma University",
            degree="B.Tech",
            branch="CSE",
            graduation_year=2028,
            cgpa=7.38,
            semester=5,
            experience_years=0,
            work_authorizations=["India"],
            external_profiles={
                "GitHub": "https://github.com/18-monarch",
                "LeetCode": "https://leetcode.com/u/Zeniitthh/",
            },
        )
    )
    db.add(
        Preferences(
            user_id=user.id,
            data=PreferenceIn(
                weekly_plan="Review hashing and trees. Explain one FleetMesh component. Apply to two verified roles."
            ).model_dump(),
        )
    )
    for name, category in [
        ("C++", "Programming"),
        ("Python", "Programming"),
        ("SQL", "Database"),
        ("React", "Frontend"),
        ("PostgreSQL", "Database"),
        ("Git", "DevOps"),
        ("OOP", "CS Fundamentals"),
    ]:
        db.add(
            UserSkill(
                user_id=user.id,
                skill_id=skill_record(db, name, category).id,
                data={
                    "proficiency": 2,
                    "confidence": 2,
                    "evidence": "Demo self-assessment: edit to reflect your actual knowledge",
                    "last_used": None,
                    "learning_status": "LEARNING",
                },
            )
        )
    for name, technologies in [
        ("FleetMesh", ["Python", "PostgreSQL"]),
        ("CrediSafe", ["React"]),
        ("CodePilot AI", []),
        ("ArthSetu AI", []),
    ]:
        p = Project(
            user_id=user.id,
            name=name,
            data={
                "description": "Seed project entry. Add your own description and verified evidence.",
                "repository_url": f"https://github.com/18-monarch/{name}"
                if name in ("FleetMesh", "CrediSafe")
                else None,
                "live_url": None,
                "technologies": technologies,
                "verified_skills": [],
                "interview_readiness": "NOT_STARTED",
            },
        )
        db.add(p)
        db.flush()
        if name == "FleetMesh":
            for topic in [
                "Architecture",
                "UDP",
                "Task allocation",
                "Dijkstra",
                "Failure handling",
                "Persistence",
            ]:
                db.add(
                    ProjectMastery(
                        project_id=p.id,
                        topic=topic,
                        data={
                            "status": "NOT_STARTED",
                            "confidence": 0,
                            "notes": "Set your own understanding level",
                            "linked_skills": [],
                        },
                    )
                )
    source = manual_source(db, user.id, "manual")
    examples = [
        (
            "Northstar Labs",
            "Software Engineer Intern",
            ["Python", "SQL", "Git"],
            ["Docker", "Testing"],
            {"minimum_cgpa": 7, "allowed_graduation_years": [2028]},
            "India",
            3,
        ),
        (
            "Aster Systems",
            "Backend Engineer Intern",
            ["Python", "PostgreSQL", "OOP"],
            ["Docker", "AWS"],
            {"minimum_cgpa": 7, "minimum_experience": 0, "allowed_graduation_years": [2028]},
            "India",
            7,
        ),
        (
            "Orbit Software",
            "Full-Stack Engineer Intern",
            ["React", "TypeScript", "SQL"],
            ["Testing", "Docker"],
            {"allowed_graduation_years": [2028]},
            "India",
            12,
        ),
        (
            "Summit Computing",
            "Software Engineer Intern",
            ["C++", "OOP"],
            ["DSA"],
            {"minimum_cgpa": 8, "allowed_graduation_years": [2028]},
            "India",
            5,
        ),
        (
            "Lattice Works",
            "Software Engineer Graduate",
            ["Python", "SQL"],
            [],
            {"allowed_graduation_years": [2026]},
            "India",
            15,
        ),
        (
            "Canal Technology",
            "Backend Engineer Intern",
            ["Python", "PostgreSQL"],
            ["Docker"],
            {"work_authorization": "Netherlands", "visa_sponsorship": False},
            "Netherlands",
            14,
        ),
        (
            "Birch Cloud",
            "Backend Engineer Intern",
            ["Python", "SQL", "Docker"],
            ["AWS", "Kubernetes"],
            {"minimum_experience": 0, "allowed_graduation_years": [2028]},
            "India",
            9,
        ),
        (
            "Meridian Digital",
            "Software Engineer Intern",
            ["Python", "Git"],
            ["Testing"],
            {},
            "Germany",
            18,
        ),
    ]
    for index, (company, title, required, preferred, req, country, days) in enumerate(examples):
        role = (
            "Backend Engineer"
            if "Backend" in title
            else "Full-Stack Engineer"
            if "Full-Stack" in title
            else "Software Engineer"
        )
        job = JobIn(
            company_name=company,
            title=title,
            normalized_role=role,
            description="SYNTHETIC DEMO — this is not a real vacancy. Build APIs, collaborate on code reviews, and write maintainable software. Required: "
            + ", ".join(required)
            + ". Preferred: "
            + ", ".join(preferred),
            external_id=f"demo-{index}",
            country=country,
            locations=["Bengaluru" if country == "India" else country],
            remote_status="hybrid",
            requirements=req,
            required_skills=required,
            preferred_skills=preferred,
            application_deadline=anchor + timedelta(days=days, hours=12),
            is_demo=True,
            posted_at=anchor,
            stipend="Demo: ₹35,000–₹60,000/month" if country == "India" else None,
        )
        upsert_job(db, user.id, job, source)
    db.commit()
    generate(db, user, "high-match")
    return user, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.environ.get("DEMO_EMAIL", "mohit@example.com"))
    args = parser.parse_args()
    password = os.environ.get("DEMO_PASSWORD")
    if not password or len(password) < 12:
        raise SystemExit("Set DEMO_PASSWORD to a unique password of at least 12 characters")
    with SessionLocal() as db:
        user, created = seed(db, args.email, password)
        print(
            f"{'Created demo account' if created else 'Account already exists; unchanged'}: {user.email}"
        )


if __name__ == "__main__":
    main()
