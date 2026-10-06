import asyncio
from unittest.mock import AsyncMock, patch

import httpx
from careeros.models import Job, Occurrence, Source, SourceRun
from careeros.schemas import JobIn
from careeros.services.ingestion import ingest_source
from careeros.services.locking import job_lock
from careeros.services.repository import upsert_job
from careeros.services.sources import Ashby, Greenhouse, Lever, OfficialFeed, fetch_json
from sqlalchemy import select


def test_adapter_normalization():
    config = {"board": "acme", "company_name": "Acme", "country": "India"}
    g = Greenhouse(config).normalize_job(
        {
            "id": 123,
            "title": "Backend Engineer Intern",
            "content": "<p>Required: Python</p><p>Preferred: Docker</p>",
            "absolute_url": "https://example.com/123",
            "location": {"name": "Ahmedabad"},
        }
    )
    assert g.external_id == "123" and g.normalized_role == "Backend Engineer"
    assert g.preferred_skills == ["Docker"]
    lever = Lever(config).normalize_job(
        {
            "id": "x",
            "text": "Software Engineer",
            "descriptionPlain": "Python",
            "categories": {"location": "India"},
            "applyUrl": "https://example.com/x",
            "salaryRange": {"min": 10000, "max": 20000, "currency": "INR", "interval": "month"},
        }
    )
    assert lever.salary_min == 10000
    a = Ashby(config).normalize_job(
        {
            "id": "a",
            "title": "Intern",
            "descriptionPlain": "Python",
            "isRemote": True,
            "applyUrl": "https://example.com/a",
        }
    )
    assert a.remote_status == "remote"


def test_ingestion_isolated_errors_idempotent_and_health(db, user):
    source = Source(
        user_id=user.id,
        name="Test board",
        kind="greenhouse",
        config={"board": "test", "country": "India"},
        enabled=True,
    )
    db.add(source)
    db.commit()
    raw = {
        "id": 321,
        "title": "Software Engineer Intern",
        "content": "Python",
        "absolute_url": "https://example.com/321",
        "location": {"name": "India"},
    }
    with patch.object(Greenhouse, "fetch_jobs", AsyncMock(return_value=[raw, {"bad": True}])):
        first = asyncio.run(ingest_source(db, source))
        assert first["added"] == 1 and first["parse_errors"] == 1 and first["status"] == "DEGRADED"
        second = asyncio.run(ingest_source(db, source))
        assert second["updated"] == 1 and second["added"] == 0
    assert db.scalar(select(SourceRun).where(SourceRun.source_id == source.id))
    with patch.object(
        Greenhouse, "fetch_jobs", AsyncMock(side_effect=httpx.ConnectError("blocked"))
    ):
        assert asyncio.run(ingest_source(db, source))["status"] == "FAILED"
    assert len(list(db.scalars(select(Job).where(Job.external_id == "321")))) == 1


def test_cross_source_dedup_keeps_occurrences_and_distinct_requisitions(db, user):
    sources = [
        Source(user_id=user.id, name=name, kind="official", config={})
        for name in ["First", "Second"]
    ]
    db.add_all(sources)
    db.flush()
    base = {
        "company_name": "Acme",
        "title": "Software Engineer Intern",
        "country": "India",
        "locations": ["Ahmedabad"],
        "source": "official",
        "requisition_id": "req-1",
        "application_url": "https://example.com/job/1",
    }
    a, _ = upsert_job(db, user.id, JobIn(**base, external_id="a"), sources[0])
    b, created = upsert_job(db, user.id, JobIn(**base, external_id="b"), sources[1])
    assert a.id == b.id and not created
    assert len(list(db.scalars(select(Occurrence).where(Occurrence.job_id == a.id)))) == 2
    c, created = upsert_job(
        db,
        user.id,
        JobIn(
            **{**base, "requisition_id": "req-2", "application_url": "https://example.com/job/2"},
            external_id="c",
        ),
        sources[0],
    )
    assert c.id != a.id and created


def test_source_retry_and_no_redirect():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503 if len(calls) < 3 else 200, json={"jobs": []})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("careeros.services.sources.asyncio.sleep", AsyncMock()):
                return await fetch_json("https://example.com/jobs", client)

    assert asyncio.run(run()) == {"jobs": []}
    assert len(calls) == 3 and "CareerOS" in calls[0].headers["User-Agent"]


def test_official_feed_not_allowlisted_is_blocked():
    import pytest

    with pytest.raises(ValueError):
        asyncio.run(OfficialFeed({"feed_url": "https://127.0.0.1/secret"}).fetch_jobs())


def test_duplicate_worker_lock(db):
    with job_lock(db.bind, "test-run") as first:
        assert first
        with job_lock(db.bind, "test-run") as second:
            assert not second
