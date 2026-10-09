import html
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx
from careeros.config import get_settings
from careeros.db import utcnow
from careeros.models import Application, Notification
from careeros.services.analytics import funnel
from careeros.services.eligibility import unconfirmed
from careeros.services.matching import skill_gaps
from careeros.services.outbound import post_json
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
            await post_json(
                client,
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Idempotency-Key": key,
                },
                payload={
                    "from": settings.email_from,
                    "to": [recipient],
                    "subject": title,
                    "html": f"<pre>{html.escape(body)}</pre>",
                },
            )
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
        already_tracked = {a.job_id for a in applications}
        for job in jobs:
            if job["match"]["classification"] == "APPLY_NOW" and job["id"] not in already_tracked:
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
            if unconfirmed(job.get("provenance", {}), "application_deadline"):
                continue
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
            actions = (
                [("OA", app.data.get("oa_deadline"))]
                if app.status in ("APPLIED", "OA_RECEIVED")
                else []
            ) + [("Interview", d) for d in app.data.get("interview_dates", [])]
            if app.status in ("REJECTED", "WITHDRAWN", "EXPIRED", "OFFER"):
                continue
            for label, date in actions:
                if not date:
                    continue
                when = datetime.fromisoformat(date.replace("Z", "+00:00"))
                if when.tzinfo:
                    when = when.astimezone(UTC).replace(tzinfo=None)
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
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if kind == "weekly":
            start = now - timedelta(days=7)
        relevant = [j for j in jobs if start <= j["created_at"] <= now]
        metrics = funnel(applications)
        gaps = skill_gaps(jobs)[:3]
        period = now.strftime("%G-W%V") if kind == "weekly" else now.date().isoformat()
        title = "Weekly career summary" if kind == "weekly" else "Your daily career digest"
        submitted = {
            a.job_id
            for a in applications
            if a.status not in ("DISCOVERED", "SAVED", "PLANNING_TO_APPLY")
        }
        actionable = [
            j
            for j in jobs
            if j["id"] not in submitted
            and j["match"]["eligibility"]["state"] not in ("CLOSED", "NOT_ELIGIBLE")
        ]
        deadlines = sorted(
            [
                j
                for j in actionable
                if j["application_deadline"]
                and not unconfirmed(j.get("provenance", {}), "application_deadline")
                and now < j["application_deadline"] <= now + timedelta(days=7)
            ],
            key=lambda j: j["application_deadline"],
        )
        period_label = "in the last 7 days" if kind == "weekly" else "today (UTC)"
        new_applications = sum(
            a.applied_at is not None and start <= a.applied_at <= now for a in applications
        )
        shortlist = sorted(actionable, key=lambda job: job["is_demo"])[:5]
        opportunities = (
            "\n".join(
                f"- {'[Demo] ' if job['is_demo'] else ''}{job['company_name']} — {job['title']} "
                f"({job['country']}): {job['match']['score']}% match; "
                f"{job['match']['eligibility']['state']}. "
                f"{job.get('application_url') or job.get('source_url') or 'Open CareerOS for details.'}"
                for job in shortlist
            )
            or "No actionable opportunities recorded yet."
        )
        actions = []
        for application in applications:
            if application.status in ("REJECTED", "WITHDRAWN", "EXPIRED", "OFFER"):
                continue
            if application.status == "PLANNING_TO_APPLY":
                actions.append(f"Apply: {application.job.company.name} — {application.job.title}")
            if application.status in ("APPLIED", "OA_RECEIVED") and application.data.get(
                "oa_deadline"
            ):
                actions.append(
                    f"OA: {application.job.company.name} — {application.data['oa_deadline']} UTC"
                )
            actions.extend(
                f"Interview: {application.job.company.name} — {d} UTC"
                for d in application.data.get("interview_dates", [])
                if datetime.fromisoformat(d.replace("Z", "+00:00")).replace(tzinfo=None) >= now
            )
        body = (
            f"{len(relevant)} opportunities discovered {period_label}. "
            f"{sum(j['match']['classification'] == 'APPLY_NOW' for j in actionable)} ready to apply. "
            f"{new_applications} applications submitted {period_label}.\n"
            f"All-time funnel ({metrics['sample_size']} applications): {metrics['recommendation']}\n"
            f"Learning priorities: {', '.join(g['skill'] for g in gaps) or 'No missing skills in relevant postings yet'}.\n"
            f"Opportunities to review (check original requirements):\n{opportunities}\n"
            "Deadlines in the next 7 days:\n"
            + (
                "\n".join(
                    f"- {j['company_name']} — {j['title']}: {j['application_deadline'].isoformat()} UTC"
                    for j in deadlines[:10]
                )
                or "None recorded."
            )
            + "\nApplication actions:\n"
            + ("\n".join(f"- {a}" for a in actions[:10]) or "None recorded.")
        )
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


def meaningful_updates(db, user):
    """Only new/materially changed relevant postings produce research alerts."""
    import hashlib
    import json

    from careeros.services.categories import CATEGORIES

    prefs = profile_data(db, user)["preferences"]
    created = 0
    for job in ranked_jobs(db, user):
        categories = set(job.get("categories", [])) & set(prefs.get("career_categories", []))
        if not categories or job["is_demo"] or job["country"] not in prefs.get("countries", []):
            continue
        if job["match"]["eligibility"]["state"] in ("CLOSED", "NOT_ELIGIBLE"):
            continue
        material = {
            key: job.get(key)
            for key in (
                "description",
                "requirements",
                "application_deadline",
                "application_url",
                "country",
            )
        }
        digest = hashlib.sha256(
            json.dumps(material, sort_keys=True, default=str).encode()
        ).hexdigest()[:24]
        title = f"Internship update: {job['company_name']}"[:240]
        m = job["match"]
        body = (
            f"{job['title']} · {job['country']}\n"
            f"Categories: {', '.join(CATEGORIES[c] for c in sorted(categories))}\n"
            f"Eligibility: {m['eligibility']['state']}. {' '.join(m['eligibility']['reasons'])}\n"
            f"Matching skills: {', '.join(m['strong_matches']) or 'Add your skills to assess fit'}.\n"
            f"Prepare: {', '.join(m['missing_required'][:4]) or 'Review requirements and explain relevant project work'}.\n"
            f"Deadline: {job['application_deadline'] or 'Not published'}\n"
            f"{job['application_url'] or job['source_url']}\n"
            "Newly discovered or materially updated; discovery time is not a posting date."
        )
        created += create_notification(
            db, user.id, f"research:{job['id']}:{digest}", "research", title, body
        )
    db.commit()
    return created
