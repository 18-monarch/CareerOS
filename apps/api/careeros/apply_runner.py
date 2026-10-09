"""Run with python -m careeros.apply_runner --email you@example.com [--submit] [--watch]."""

import argparse
import asyncio
import base64
import hashlib
import json
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from careeros.db import SessionLocal, utcnow
from careeros.models import (
    Application,
    ApplicationDraft,
    ApplicationEvent,
    AuditLog,
    Job,
    ResumeVersion,
    User,
)
from careeros.schemas import ApplicationIn
from careeros.services.application_desk import (
    can_auto_approve,
    current_blockers,
    settings_for,
    supported_url,
)
from careeros.services.locking import job_lock
from careeros.services.research import verify_posting


def record_result(db, user, draft, result):
    status = result.get("status")
    if status not in ("SUBMITTED", "UNCERTAIN", "HANDOFF", "PREVIEWED"):
        status = "UNCERTAIN"
    draft.status = "APPROVED" if status == "PREVIEWED" else status
    draft.data = {**draft.data, "result": result, "attempt_finished": utcnow().isoformat()}
    if status == "SUBMITTED":
        app = db.scalar(
            select(Application).where(
                Application.user_id == user.id, Application.job_id == draft.job_id
            )
        )
        if not app:
            app = Application(
                user_id=user.id,
                job_id=draft.job_id,
                data=ApplicationIn(job_id=draft.job_id).model_dump(
                    mode="json", exclude={"job_id", "status"}
                ),
            )
            db.add(app)
            db.flush()
        app.status, app.applied_at = "APPLIED", utcnow()
        app.data = {
            **app.data,
            "resume_id": draft.data["packet"]["resume_id"],
            "submission_evidence": result,
            "draft_id": draft.id,
        }
        app.events.append(
            ApplicationEvent(
                status="APPLIED", note="Local browser observed employer submission confirmation."
            )
        )
    db.commit()


def process(db, user, submit=False, headless=False, executor=None, verifier=None):
    cfg = settings_for(db, user)
    with job_lock(db.bind, f"apply:{user.id}") as acquired:
        if not acquired:
            return []
        rows = list(
            db.scalars(
                select(ApplicationDraft)
                .where(ApplicationDraft.user_id == user.id)
                .order_by(ApplicationDraft.created_at)
            )
        )
        today = utcnow().date().isoformat()
        attempts = len(
            list(
                db.scalars(
                    select(AuditLog).where(
                        AuditLog.user_id == user.id,
                        AuditLog.action == "application.submit_attempt",
                        AuditLog.created_at >= datetime.fromisoformat(today),
                    )
                )
            )
        )
        results = []
        for draft in rows:
            if draft.status == "SUBMITTING":
                record_result(
                    db,
                    user,
                    draft,
                    {
                        "status": "UNCERTAIN",
                        "reason": "Previous runner stopped during an attempt. Verify its outcome manually.",
                    },
                )
                continue
            if draft.status == "DRAFT" and can_auto_approve(db, user, draft):
                draft.status = "APPROVED"
                draft.data = {
                    **draft.data,
                    "approved_at": utcnow().isoformat(),
                    "approval": "saved_policy",
                }
                db.commit()
            if draft.status != "APPROVED" or (submit and attempts >= cfg["daily_limit"]):
                continue
            blockers = current_blockers(db, user, draft)
            if blockers or not supported_url(draft.data["url"]):
                record_result(
                    db,
                    user,
                    draft,
                    {
                        "status": "HANDOFF",
                        "reason": " ".join(blockers)
                        or "This employer site requires manual application. The prepared packet is available in Application desk.",
                    },
                )
                continue
            approved = datetime.fromisoformat(draft.data["approved_at"])
            if utcnow() - approved > timedelta(hours=24):
                record_result(
                    db,
                    user,
                    draft,
                    {
                        "status": "HANDOFF",
                        "reason": "Approval is over 24 hours old. Refresh the posting and prepare/review again.",
                    },
                )
                continue
            if submit:
                fresh, _, status, reason = asyncio.run(
                    (verifier or verify_posting)(draft.data["url"])
                )
                job = db.get(Job, draft.job_id)
                if status != "VERIFIED_LISTING" or fresh is None:
                    record_result(
                        db,
                        user,
                        draft,
                        {
                            "status": "HANDOFF",
                            "reason": "Live pre-submission check failed: " + reason,
                        },
                    )
                    continue
                if fresh.title != job.title or fresh.description != job.description:
                    record_result(
                        db,
                        user,
                        draft,
                        {
                            "status": "HANDOFF",
                            "reason": "The employer posting changed. Review the latest posting, update it in CareerOS and prepare again.",
                        },
                    )
                    continue
            resume = db.get(ResumeVersion, draft.data["packet"]["resume_id"])
            content = resume.data["content_base64"]
            if (
                hashlib.sha256(base64.b64decode(content)).hexdigest()
                != draft.data["packet"]["resume_sha256"]
            ):
                record_result(
                    db,
                    user,
                    draft,
                    {"status": "HANDOFF", "reason": "Resume content changed; prepare again."},
                )
                continue
            payload = {
                "url": draft.data["url"],
                "packet": draft.data["packet"],
                "resume": content,
                "submit": submit,
                "headless": headless,
            }
            if submit:
                db.add(
                    AuditLog(
                        user_id=user.id, action="application.submit_attempt", target_id=draft.id
                    )
                )
                draft.status = "SUBMITTING"
                draft.data = {**draft.data, "attempt_started": utcnow().isoformat()}
                db.commit()
                attempts += 1
            try:
                if executor:
                    result = executor(payload)
                else:
                    script = Path(__file__).resolve().parents[3] / "scripts/application-browser.mjs"
                    completed = subprocess.run(
                        ["node", str(script)],
                        input=json.dumps(payload),
                        text=True,
                        capture_output=True,
                        timeout=120,
                        check=False,
                    )
                    result = json.loads(completed.stdout.strip().splitlines()[-1])
            except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
                result = {
                    "status": "UNCERTAIN" if submit else "HANDOFF",
                    "reason": "Browser runner did not return a result. Verify the employer outcome before retrying. Check Node and Playwright Chromium installation.",
                }
            record_result(db, user, draft, result)
            results.append({"draft_id": draft.id, **result})
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email")
    parser.add_argument(
        "--interactive", action="store_true", help="Prompt for account and explicit submission mode"
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Process approved applications; without this flag only preview/fill checks run.",
    )
    parser.add_argument(
        "--watch", action="store_true", help="Check approved queue every 30 seconds"
    )
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    if args.interactive:
        args.email = input("Your CareerOS account email: ").strip()
        args.submit = (
            input(
                "Type SUBMIT to process approved applications, or Enter for preview only: "
            ).strip()
            == "SUBMIT"
        )
        args.watch = args.submit
    if not args.email:
        parser.error("--email is required unless --interactive is used")
    while True:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == args.email.lower()))
            if not user:
                raise SystemExit("Account not found. Use the same database/.env as CareerOS.")
            print(json.dumps(process(db, user, args.submit, args.headless)), flush=True)
        if not args.watch:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
