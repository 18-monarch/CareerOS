import argparse
import asyncio
import json

from careeros.db import SessionLocal, engine, utcnow
from careeros.logging_config import configure_logging
from careeros.models import AuthSession, Job, MatchResult, Source, User
from careeros.services.eligibility import unconfirmed
from careeros.services.ingestion import ingest_source
from careeros.services.locking import job_lock
from careeros.services.notifications import deliver, generate
from careeros.services.repository import ranked_jobs
from sqlalchemy import delete, select

logger = configure_logging()

COMMANDS = [
    "ingest-jobs",
    "refresh-jobs",
    "calculate-matches",
    "expire-jobs",
    "send-daily-digest",
    "send-deadline-alerts",
    "weekly-summary",
    "run-cycle",
    "discover-jobs",
]


async def run(command):
    with job_lock(engine, command) as acquired:
        if not acquired:
            return {"status": "skipped", "reason": "another execution holds the lock"}
        if command == "discover-jobs":
            from careeros.services.discovery import run_due

            return {"command": command, **await run_due()}
        if command == "run-cycle":
            stages = []
            for stage in (
                "ingest-jobs",
                "calculate-matches",
                "expire-jobs",
                "send-deadline-alerts",
            ):
                try:
                    stages.append(await run(stage))
                except Exception as exc:
                    logger.error(
                        "worker_stage_failed",
                        extra={"error_type": type(exc).__name__, "command": stage},
                    )
                    stages.append({"command": stage, "errors": 1})
            return {
                "command": command,
                "stages": stages,
                "errors": sum(s.get("errors", 0) for s in stages),
            }
        summary = {"command": command, "processed": 0, "errors": 0}
        with SessionLocal() as db:
            if command in ("ingest-jobs", "refresh-jobs"):
                for source in list(db.scalars(select(Source).where(Source.enabled.is_(True)))):
                    result = await ingest_source(db, source)
                    summary["processed"] += result["added"] + result["updated"]
                    summary["errors"] += int(result["status"] in ("FAILED", "DEGRADED"))
            elif command == "expire-jobs":
                for job in db.scalars(select(Job).where(Job.is_active.is_(True))):
                    if any(
                        getattr(job, key)
                        and getattr(job, key) <= utcnow()
                        and not unconfirmed(job.requirements.provenance, key)
                        for key in ("application_deadline", "expires_at")
                    ):
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
