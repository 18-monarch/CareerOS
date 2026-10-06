import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from careeros.db import utcnow
from careeros.main import app
from careeros.manage import manage_user
from careeros.models import Application, AuthSession, Job, Notification, Occurrence, Source, User
from careeros.schemas import JobIn
from careeros.services.ingestion import ingest_source
from careeros.services.locking import job_lock
from careeros.services.notifications import generate
from careeros.services.repository import company_record, skill_record, upsert_job
from careeros.services.sources import Greenhouse
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


def raw_job(id="one", title="Software Engineer Intern"):
    return {
        "id": id,
        "title": title,
        "content": "Required: Python\nPreferred: Docker",
        "absolute_url": f"https://example.com/jobs/{id}",
        "location": {"name": "India"},
    }


def source(db, user, name="Reliable board"):
    row = Source(
        user_id=user.id,
        name=name,
        kind="greenhouse",
        config={
            "board": "sample",
            "company_name": "Reliability Co",
            "country": "India",
            "close_missing_after": 2,
        },
    )
    db.add(row)
    db.commit()
    return row


def ingest(db, src, rows):
    with patch.object(Greenhouse, "fetch_jobs", AsyncMock(return_value=rows)):
        return asyncio.run(ingest_source(db, src))


def test_reconciliation_requires_two_complete_snapshots_and_reopens(db, user):
    src = source(db, user)
    a, b = raw_job(), raw_job("two", "Backend Engineer")
    ingest(db, src, [a, b])
    job = db.scalar(select(Job).where(Job.external_id == "one"))
    assert ingest(db, src, [b])["closed"] == 0
    assert job.is_active
    assert ingest(db, src, [b])["closed"] == 1
    assert not job.is_active and job.data["source_closed"]
    assert ingest(db, src, [a, b])["updated"] == 2
    assert job.is_active and not job.data["source_closed"]


def test_empty_failed_and_partial_feeds_do_not_close_jobs(db, user):
    src = source(db, user)
    a, b = raw_job(), raw_job("two", "Backend Engineer")
    ingest(db, src, [a, b])
    job = db.scalar(select(Job).where(Job.external_id == "one"))
    for _ in range(3):
        ingest(db, src, [])
        result = ingest(db, src, [b, {"malformed": True}])
        assert result["status"] == "DEGRADED"
    occurrence = db.scalar(select(Occurrence).where(Occurrence.job_id == job.id))
    assert job.is_active and occurrence.missing_runs == 0


def test_other_source_keeps_canonical_job_open(db, user):
    first, second = source(db, user), source(db, user, "Second board")
    a, b = raw_job(), raw_job("two", "Backend Engineer")
    ingest(db, first, [a, b])
    ingest(db, second, [a])
    ingest(db, first, [b])
    ingest(db, first, [b])
    job = db.scalar(select(Job).where(Job.external_id == "one"))
    assert job.is_active
    rows = list(db.scalars(select(Occurrence).where(Occurrence.job_id == job.id)))
    assert len(rows) == 2 and sum(o.is_active for o in rows) == 1


def test_archive_survives_refresh_and_can_be_restored(logged, db, user):
    src = source(db, user)
    ingest(db, src, [raw_job()])
    job = db.scalar(select(Job).where(Job.external_id == "one"))
    assert logged.patch(f"/jobs/{job.id}/archive").status_code == 200
    ingest(db, src, [raw_job()])
    assert not job.is_active
    assert logged.get(f"/jobs/{job.id}/eligibility").json()["state"] == "CLOSED"
    assert logged.patch(f"/jobs/{job.id}/restore").status_code == 200
    assert logged.get(f"/jobs/{job.id}").json()["is_active"]


def test_secondary_board_cannot_overwrite_primary_facts(db, user):
    first, second = source(db, user), source(db, user, "Second board")
    body = JobIn(
        company_name="Primary Co",
        title="Original role",
        application_url="https://example.com/same",
        source="greenhouse",
        external_id="1",
    )
    job, _ = upsert_job(db, user.id, body, first)
    upsert_job(db, user.id, body.model_copy(update={"title": "Secondary role"}), second)
    upsert_job(db, user.id, body.model_copy(update={"title": "Secondary refresh"}), second)
    assert job.title == "Original role"


def test_source_edits_preserve_imported_identity(logged, db, user):
    body = {
        "name": "Typo",
        "kind": "greenhouse",
        "board": "wrong",
        "company_name": "Reliable",
        "country": "India",
    }
    id = logged.post("/sources", json=body).json()["id"]
    body.update(board="right", name="Correct board", close_missing_after=2)
    assert logged.put(f"/sources/{id}", json=body).status_code == 200
    src = db.get(Source, id)
    ingest(db, src, [raw_job()])
    body["board"] = "another"
    assert logged.put(f"/sources/{id}", json=body).status_code == 409
    body.update(board="right", name="Renamed source")
    assert logged.put(f"/sources/{id}", json=body).status_code == 200
    body["close_missing_after"] = 1
    assert logged.put(f"/sources/{id}", json=body).status_code == 422


def test_manual_mutation_respects_ingestion_lock(logged, db, user):
    with job_lock(db.bind, f"ingest-user:{user.id}"):
        response = logged.post("/jobs", json={"company_name": "Busy", "title": "Busy"})
    assert response.status_code == 409


def test_shared_identity_creation_survives_parallel_writers(db):
    def write(_):
        with Session(db.bind) as session:
            skill = skill_record(session, "Concurrent Skill")
            company = company_record(session, "Concurrent Co")
            ids = skill.id, company.id
            session.commit()
            return ids

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(write, range(12)))
    assert len(set(ids)) == 1


def test_password_change_revokes_other_sessions(logged, db, user):
    other = TestClient(app)
    assert (
        other.post(
            "/auth/login", json={"email": user.email, "password": "Test-password-12345"}
        ).status_code
        == 200
    )
    assert (
        logged.post(
            "/auth/password",
            json={"current_password": "incorrect", "new_password": "New-valid-password-123"},
        ).status_code
        == 400
    )
    result = logged.post(
        "/auth/password",
        json={"current_password": "Test-password-12345", "new_password": "New-valid-password-123"},
    )
    assert result.status_code == 200
    assert logged.get("/auth/me").status_code == 200
    assert other.get("/auth/me").status_code == 401
    assert len(list(db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)))) == 1
    assert (
        other.post(
            "/auth/login", json={"email": user.email, "password": "New-valid-password-123"}
        ).status_code
        == 200
    )


def test_password_spaces_are_significant(client):
    body = {"email": "spaces@example.com", "password": " password-with-spaces "}
    assert client.post("/auth/register", json=body).status_code == 201
    assert (
        client.post("/auth/login", json={**body, "password": body["password"].strip()}).status_code
        == 401
    )
    assert client.post("/auth/login", json=body).status_code == 200


def test_operator_bootstrap_and_recovery(db):
    id = manage_user(db, "owner@example.com", "First-long-password-123", "Owner")
    with pytest.raises(ValueError):
        manage_user(db, "owner@example.com", "Second-long-password-123")
    assert manage_user(db, "owner@example.com", "Recovered-password-123", reset=True) == id
    assert db.get(User, id).name == "Owner"


def test_real_body_limit_rejects_chunked_and_bad_length(client):
    response = client.post("/auth/login", content=(b"x" * 600000 for _ in range(2)))
    assert response.status_code == 413
    response = client.post("/auth/login", content=b"{}", headers={"Content-Length": "invalid"})
    assert response.status_code == 400


def test_weekly_digest_includes_earlier_discoveries_and_actions(db, user):
    now = utcnow().replace(hour=12)
    # Use a fixed Wednesday so this is stable on every day of the week.
    now -= timedelta(days=(now.weekday() - 2) % 7)
    jobs = list(db.scalars(select(Job).where(Job.user_id == user.id)).unique())
    for job in jobs:
        job.created_at = now - timedelta(days=2)
    db.commit()
    with patch("careeros.services.notifications.utcnow", return_value=now):
        assert generate(db, user, "weekly") == 1
        assert generate(db, user, "weekly") == 0
    notification = db.scalar(select(Notification).where(Notification.kind == "weekly"))
    assert "8 opportunities discovered in the last 7 days" in notification.body
    assert (
        "Deadlines in the next 7 days" in notification.body
        and "Application actions" in notification.body
    )


def test_completed_oa_does_not_generate_an_oa_reminder(db, user):
    job = db.scalar(select(Job).where(Job.user_id == user.id))
    application = Application(
        user_id=user.id,
        job_id=job.id,
        status="OA_COMPLETED",
        data={"oa_deadline": (utcnow() + timedelta(days=1)).isoformat()},
    )
    db.add(application)
    db.commit()
    generate(db, user, "deadline")
    assert not db.scalar(
        select(Notification).where(Notification.dedupe_key.like(f"action:{application.id}:OA:%"))
    )


def test_resume_edit_and_used_resume_delete_protection(logged):
    body = {"name": "Master", "is_master": True, "version": "1"}
    id = logged.post("/resumes", json=body).json()["id"]
    assert logged.put(f"/resumes/{id}", json={**body, "version": "2"}).json()["version"] == "2"
    job_id = logged.get("/jobs").json()["items"][0]["id"]
    assert logged.post("/applications", json={"job_id": job_id, "resume_id": id}).status_code == 201
    assert logged.delete(f"/resumes/{id}").status_code == 409


def test_worker_cycle_continues_after_source_stage_failure(db):
    from worker import __main__ as worker

    calls = []
    original_run = worker.run

    async def stage(command):
        calls.append(command)
        if command == "ingest-jobs":
            raise RuntimeError("Upstream unavailable")
        return {"command": command, "errors": 0}

    with patch.object(worker, "engine", db.bind), patch.object(worker, "run", side_effect=stage):
        result = asyncio.run(original_run("run-cycle"))
    assert result["errors"] == 1
    assert calls == ["ingest-jobs", "calculate-matches", "expire-jobs", "send-deadline-alerts"]


def test_unconfirmed_deadline_requires_review_instead_of_closing():
    from careeros.services.eligibility import evaluate

    profile = {"work_authorizations": ["India"]}
    job = {
        "country": "India",
        "application_deadline": "2020-01-01T00:00:00Z",
        "provenance": {"application_deadline": {"method": "ai", "confirmed": False}},
    }
    assert evaluate(profile, job)["state"] == "REVIEW_REQUIRED"
    job["provenance"]["application_deadline"]["confirmed"] = True
    assert evaluate(profile, job)["state"] == "CLOSED"


def test_skill_category_edit_is_per_user(logged):
    body = {"name": "Python", "category": "Backend", "proficiency": 3}
    assert logged.post("/skills", json=body).status_code == 201
    assert (
        next(s for s in logged.get("/skills").json() if s["name"] == "python")["category"]
        == "Backend"
    )


def test_ready_rejects_outdated_schema(db, client):
    from careeros import main
    from sqlalchemy import text

    db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
    db.execute(text("INSERT INTO alembic_version VALUES ('8f22a1')"))
    db.commit()
    try:
        with patch.object(main, "engine", db.bind):
            assert client.get("/ready").status_code == 503
            db.execute(text("UPDATE alembic_version SET version_num = 'c61f03'"))
            db.commit()
            assert client.get("/ready").status_code == 200
    finally:
        db.execute(text("DROP TABLE alembic_version"))
        db.commit()


@pytest.mark.parametrize("idempotent,expected_calls", [(True, 3), (False, 1)])
def test_provider_retries_preserve_idempotency(idempotent, expected_calls):
    import httpx
    from careeros.services.outbound import post_json

    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["User-Agent"].startswith("CareerOS")
        if idempotent:
            assert request.headers["Idempotency-Key"] == "stable-test-key"
        return httpx.Response(503)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=1) as client:
            with patch("careeros.services.outbound.asyncio.sleep", AsyncMock()):
                await post_json(
                    client,
                    "https://example.com/provider",
                    headers={"Idempotency-Key": "stable-test-key"} if idempotent else {},
                    payload={},
                )

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(run())
    assert len(calls) == expected_calls
