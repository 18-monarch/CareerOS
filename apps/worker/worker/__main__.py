import argparse
import asyncio
import json

from careeros.db import SessionLocal, engine, utcnow
from careeros.models import AuthSession, Job, MatchResult, Source, User
from careeros.services.ingestion import ingest_source
from careeros.services.locking import job_lock
from careeros.services.notifications import deliver, generate
from careeros.services.repository import ranked_jobs
from sqlalchemy import delete, select

COMMANDS = [
    "ingest-jobs",
    "refresh-jobs",
    "calculate-matches",
    "expire-jobs",
    "send-daily-digest",
    "send-deadline-alerts",
    "weekly-summary",
]


async def run(command):
    with job_lock(engine, command) as acquired:
        if not acquired:
            return {"status": "skipped", "reason": "another execution holds the lock"}
        summary = {"command": command, "processed": 0, "errors": 0}
        with SessionLocal() as db:
            if command in ("ingest-jobs", "refresh-jobs"):
                for source in list(db.scalars(select(Source).where(Source.enabled.is_(True)))):
                    result = await ingest_source(db, source)
                    summary["processed"] += result["added"] + result["updated"]
                    summary["errors"] += int(result["status"] == "FAILED")
            elif command == "expire-jobs":
                for job in db.scalars(select(Job).where(Job.is_active.is_(True))):
                    if any(d and d <= utcnow() for d in [job.application_deadline, job.expires_at]):
                        job.is_active = False
                        summary["processed"] += 1
                db.execute(delete(AuthSession).where(AuthSession.expires <= utcnow()))
                db.commit()
            for user in list(db.scalars(select(User))):
                if command == "calculate-matches":
                    for job in ranked_jobs(db, user):
                        row = db.scalar(
                            select(MatchResult).where(
                                MatchResult.user_id == user.id, MatchResult.job_id == job["id"]
                            )
                        )
                        if not row:
                            row = MatchResult(user_id=user.id, job_id=job["id"])
                            db.add(row)
                        row.data = job["match"]
                        summary["processed"] += 1
                    db.commit()
                kind = {
                    "send-daily-digest": "daily",
                    "send-deadline-alerts": "deadline",
                    "weekly-summary": "weekly",
                    "ingest-jobs": "high-match",
                    "refresh-jobs": "high-match",
                }.get(command)
                if kind:
                    with job_lock(engine, f"notify:{user.id}") as locked:
                        if locked:
                            summary["processed"] += generate(db, user, kind)
                            await deliver(db, user)
        return summary


def main():
    parser = argparse.ArgumentParser(description="CareerOS scheduled processing")
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args()
    result = asyncio.run(run(args.command))
    print(json.dumps(result))
    return 1 if result.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
