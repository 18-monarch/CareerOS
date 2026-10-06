import html
from datetime import datetime
from typing import Protocol

import httpx
from careeros.config import get_settings
from careeros.db import utcnow
from careeros.models import Application, Notification
from careeros.services.analytics import funnel
from careeros.services.matching import skill_gaps
from careeros.services.repository import profile_data, ranked_jobs
from sqlalchemy import select


class EmailProvider(Protocol):
    async def send(self, recipient: str, title: str, body: str, key: str): ...


class NoEmail:
    async def send(self, recipient, title, body, key):
        return False


class ResendEmail:
    async def send(self, recipient, title, body, key):
        settings = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Idempotency-Key": key,
                },
                json={
                    "from": settings.email_from,
                    "to": [recipient],
                    "subject": title,
                    "html": f"<pre>{html.escape(body)}</pre>",
                },
            )
            response.raise_for_status()
        return True


def create_notification(db, user_id, key, kind, title, body):
    existing = db.scalar(
        select(Notification).where(Notification.user_id == user_id, Notification.dedupe_key == key)
    )
    if existing:
        return False
    db.add(Notification(user_id=user_id, dedupe_key=key, kind=kind, title=title, body=body))
    db.flush()
    return True


def generate(db, user, kind):
    now = utcnow()
    jobs = ranked_jobs(db, user)
    prefs = profile_data(db, user)["preferences"]
    applications = list(
        db.scalars(select(Application).where(Application.user_id == user.id)).unique()
    )
    created = 0
    if kind == "high-match":
        for job in jobs:
            if job["match"]["classification"] == "APPLY_NOW":
                created += create_notification(
                    db,
                    user.id,
                    f"high:{job['id']}",
                    kind,
                    f"Strong match: {job['company_name']}",
                    f"{job['title']} · {job['match']['score']}% match. {'Synthetic demo opportunity.' if job['is_demo'] else 'Review the original posting before applying.'}",
                )
    elif kind == "deadline":
        for job in jobs:
            deadline = job["application_deadline"]
            if not deadline or job["match"]["eligibility"]["state"] in ("CLOSED", "NOT_ELIGIBLE"):
                continue
            if any(
                a.job_id == job["id"]
                and a.status not in ("DISCOVERED", "SAVED", "PLANNING_TO_APPLY")
                for a in applications
            ):
                continue
            days = (deadline - now).total_seconds() / 86400
            thresholds = [d for d in prefs.get("deadline_days", [7, 3, 1]) if 0 < days <= d]
            if thresholds:
                threshold = min(thresholds)
                created += create_notification(
                    db,
                    user.id,
                    f"deadline:{job['id']}:{deadline.isoformat()}:{threshold}",
                    kind,
                    f"Apply within {threshold} day(s): {job['company_name']}",
                    f"{job['title']} closes {deadline.isoformat()} UTC. {'Synthetic demo.' if job['is_demo'] else ''}",
                )
        for app in applications:
            actions = [("OA", app.data.get("oa_deadline"))] + [
                ("Interview", d) for d in app.data.get("interview_dates", [])
            ]
            if app.status in ("REJECTED", "WITHDRAWN", "EXPIRED", "OFFER"):
                continue
            for label, date in actions:
                if not date:
                    continue
                when = datetime.fromisoformat(date.replace("Z", "+00:00")).replace(tzinfo=None)
                if 0 < (when - now).total_seconds() <= 86400 * 3:
                    created += create_notification(
                        db,
                        user.id,
                        f"action:{app.id}:{label}:{date}",
                        kind,
                        f"{label} approaching: {app.job.company.name}",
                        f"{app.job.title} · {date}",
                    )
    elif kind in ("daily", "weekly"):
        relevant = [j for j in jobs if j["created_at"].date() == now.date()]
        metrics = funnel(applications)
        gaps = skill_gaps(jobs)[:3]
        period = now.strftime("%G-W%V") if kind == "weekly" else now.date().isoformat()
        title = "Weekly career summary" if kind == "weekly" else "Your daily career digest"
        body = f"{len(relevant)} opportunities discovered today. {sum(j['match']['classification'] == 'APPLY_NOW' for j in jobs)} ready to apply. {metrics['sample_size']} applications recorded.\n{metrics['recommendation']}\nLearning priorities: {', '.join(g['skill'] for g in gaps) or 'No missing skills in relevant postings yet'}.\nCheck your application deadlines in CareerOS."
        created += create_notification(db, user.id, f"{kind}:{period}", kind, title, body)
    db.commit()
    return created


async def deliver(db, user):
    prefs = profile_data(db, user)["preferences"]
    settings = get_settings()
    if not prefs.get("email_enabled") or not settings.resend_api_key or not settings.email_from:
        return 0
    provider, delivered = ResendEmail(), 0
    for n in db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id, Notification.emailed_at.is_(None))
        .order_by(Notification.created_at)
        .limit(100)
    ):
        try:
            if await provider.send(user.email, n.title, n.body, n.id):
                n.emailed_at, n.delivery_error = utcnow(), None
                delivered += 1
        except httpx.HTTPError as exc:
            n.delivery_error = f"{type(exc).__name__}; delivery will be retried"
        db.commit()
    return delivered
