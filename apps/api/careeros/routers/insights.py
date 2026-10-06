from datetime import timedelta

from careeros.db import get_db, utcnow
from careeros.models import (
    Application,
    DSALog,
    LearningProgress,
    MarketReport,
    Notification,
    User,
    VisaRule,
)
from careeros.routers.profile import owned
from careeros.schemas import DSALogIn, LearningIn, MarketIn, VisaIn
from careeros.security import current_user
from careeros.services.analytics import funnel
from careeros.services.matching import skill_gaps
from careeros.services.repository import profile_data, ranked_jobs
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Intelligence"])


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    jobs = ranked_jobs(db, user)
    applications = list(
        db.scalars(select(Application).where(Application.user_id == user.id)).unique()
    )
    application_by_job = {a.job_id: {"id": a.id, "status": a.status} for a in applications}
    for job in jobs:
        job["application"] = application_by_job.get(job["id"])
    now = utcnow()
    active = [j for j in jobs if j["match"]["eligibility"]["state"] != "CLOSED"]
    deadlines = sorted(
        [
            j
            for j in active
            if j["application_deadline"]
            and j["application_deadline"] > now
            and j["match"]["eligibility"]["state"] != "NOT_ELIGIBLE"
            and (
                not j["application"]
                or j["application"]["status"] in ("DISCOVERED", "SAVED", "PLANNING_TO_APPLY")
            )
        ],
        key=lambda j: j["application_deadline"],
    )
    return {
        "new_today": sum(j["created_at"].date() == now.date() for j in jobs),
        "active_jobs": len(active),
        "classifications": {
            c: sum(j["match"]["classification"] == c for j in active)
            for c in ["APPLY_NOW", "PREP_THEN_APPLY", "WATCH", "LOW_PRIORITY"]
        },
        "not_eligible": sum(j["match"]["eligibility"]["state"] == "NOT_ELIGIBLE" for j in jobs),
        "top_jobs": active[:4],
        "next_deadline": deadlines[0] if deadlines else None,
        "learning": skill_gaps(jobs)[:3],
        "pipeline": funnel(applications),
        "planned": sum(a.status == "PLANNING_TO_APPLY" for a in applications),
        "weekly_plan": profile_data(db, user)["preferences"].get("weekly_plan", ""),
        "demo_jobs": sum(j["is_demo"] for j in jobs),
    }


@router.get("/learning/recommendations")
def recommendations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return skill_gaps(ranked_jobs(db, user))


@router.get("/learning/progress")
def progress(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        {"id": p.id, "topic": p.topic, **p.data}
        for p in db.scalars(select(LearningProgress).where(LearningProgress.user_id == user.id))
    ]


@router.put("/learning/progress")
def update_progress(
    body: LearningIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    p = db.scalar(
        select(LearningProgress).where(
            LearningProgress.user_id == user.id, LearningProgress.topic == body.topic
        )
    )
    if not p:
        p = LearningProgress(user_id=user.id, topic=body.topic)
        db.add(p)
    p.data = body.model_dump(exclude={"topic"})
    db.commit()
    return {"id": p.id, "topic": p.topic, **p.data}


@router.get("/dsa")
def dsa(user: User = Depends(current_user), db: Session = Depends(get_db)):
    logs = list(
        db.scalars(
            select(DSALog).where(DSALog.user_id == user.id).order_by(DSALog.created_at.desc())
        )
    )
    topics = [
        "Arrays",
        "Strings",
        "Hashing",
        "Binary Search",
        "Two Pointers",
        "Sliding Window",
        "Linked Lists",
        "Stacks",
        "Queues",
        "Trees",
        "BST",
        "Heap",
        "Graphs",
        "Greedy",
        "Dynamic Programming",
    ]
    result = []
    for topic in topics:
        rows = [entry for entry in logs if entry.topic == topic]
        result.append(
            {
                "topic": topic,
                "problems_solved": len(rows),
                **{
                    k: sum(getattr(entry, k) for entry in rows)
                    for k in (
                        "independent",
                        "hint_required",
                        "could_explain",
                        "complexity_understood",
                    )
                },
                "last_reviewed": rows[0].created_at if rows else None,
            }
        )
    return {
        "topics": result,
        "logs": [
            {
                "id": entry.id,
                "topic": entry.topic,
                "problem": entry.problem,
                "created_at": entry.created_at,
                **{
                    k: getattr(entry, k)
                    for k in (
                        "independent",
                        "hint_required",
                        "could_explain",
                        "complexity_understood",
                    )
                },
            }
            for entry in logs[:100]
        ],
    }


@router.post("/dsa", status_code=201)
def log_dsa(body: DSALogIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = DSALog(user_id=user.id, **body.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id, **body.model_dump()}


@router.delete("/dsa/{id}")
def delete_dsa(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned(db, DSALog, id, user))
    db.commit()
    return {"ok": True}


@router.get("/notifications")
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        {
            "id": n.id,
            "kind": n.kind,
            "title": n.title,
            "body": n.body,
            "read": n.read,
            "created_at": n.created_at,
            "emailed_at": n.emailed_at,
            "delivery_error": n.delivery_error,
        }
        for n in db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(100)
        )
    ]


@router.patch("/notifications/{id}/read")
def mark_read(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = owned(db, Notification, id, user)
    n.read = True
    db.commit()
    return {"ok": True}


@router.get("/market-reports")
def market(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        {"id": m.id, "market": m.market, "period": m.period, **m.data}
        for m in db.scalars(
            select(MarketReport)
            .where(MarketReport.user_id == user.id)
            .order_by(MarketReport.period.desc())
        )
    ]


@router.post("/market-reports", status_code=201)
def add_market(body: MarketIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = MarketReport(
        user_id=user.id,
        market=body.market,
        period=body.period,
        data=body.model_dump(exclude={"market", "period"}),
    )
    db.add(row)
    db.commit()
    return {"id": row.id, **body.model_dump()}


@router.delete("/market-reports/{id}")
def delete_market(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned(db, MarketReport, id, user))
    db.commit()
    return {"ok": True}


@router.get("/visa-rules")
def visa_rules(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        {
            "id": v.id,
            "country": v.country,
            "last_verified": v.last_verified,
            "stale": v.last_verified < utcnow() - timedelta(days=90),
            **v.data,
        }
        for v in db.scalars(select(VisaRule).where(VisaRule.user_id == user.id))
    ]


@router.post("/visa-rules", status_code=201)
def add_visa(body: VisaIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = VisaRule(
        user_id=user.id,
        country=body.country,
        last_verified=body.last_verified.replace(tzinfo=None),
        data=body.model_dump(mode="json", exclude={"country", "last_verified"}),
    )
    db.add(row)
    db.commit()
    return {"id": row.id, **body.model_dump()}


@router.delete("/visa-rules/{id}")
def delete_visa(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned(db, VisaRule, id, user))
    db.commit()
    return {"ok": True}
