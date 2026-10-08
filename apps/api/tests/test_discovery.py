import asyncio
from datetime import timedelta
from unittest.mock import patch

from careeros.db import utcnow
from careeros.models import DiscoveryState, Job, Notification, Source, SourceRun
from careeros.schemas import JobIn
from careeros.services import discovery
from careeros.services.discovery_catalog import early_career, enrich_location
from careeros.services.locking import job_lock
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

BOARD = {
    "kind": "greenhouse",
    "board": "fixture",
    "company_name": "Real Fixture",
    "url": "https://example.com/careers",
}


class Feed:
    calls = 0

    def __init__(self, config):
        self.config = config

    async def fetch_jobs(self):
        Feed.calls += 1
        if self.config["board"] == "broken":
            raise ValueError("offline")
        return [
            {"title": "Software Engineer Intern", "external_id": "1"},
            {"title": "Senior Software Engineer", "external_id": "2"},
            {"title": "Talent Acquisition Intern", "external_id": "3"},
        ]

    def normalize_job(self, raw):
        return JobIn(
            **raw,
            company_name="Real Fixture",
            source="greenhouse",
            country="Unknown",
            locations=["Bengaluru"],
            description="Python internship; graduation year not stated",
            required_skills=["Python"],
        )


def run(db, catalog=(BOARD,)):
    factory = sessionmaker(db.bind, expire_on_commit=False)
    with (
        patch.object(discovery, "CATALOG", catalog),
        patch("careeros.services.ingestion.ADAPTERS", {"greenhouse": Feed}),
    ):
        result = asyncio.run(discovery.run_due(factory))
    db.expire_all()
    return result


def test_automatic_first_scan_relevance_schedule_and_repeat(db, user, logged):
    Feed.calls = 0
    assert run(db)["errors"] == 0
    state = db.scalar(select(DiscoveryState).where(DiscoveryState.user_id == user.id))
    assert state.status == "HEALTHY"
    assert state.summary["added"] == 1
    assert state.summary["skipped"] == 2
    assert state.summary["live_opportunities"] == 1
    assert state.next_run > utcnow() + timedelta(hours=5)
    job = db.scalar(select(Job).where(Job.is_demo.is_(False)))
    assert job.country == "India"
    assert job.requirements.provenance["country"]["confirmed"] is False
    count = db.scalar(select(func.count()).select_from(Notification))
    digest = db.scalar(select(Notification).where(Notification.kind == "daily"))
    assert "Real Fixture — Software Engineer Intern" in digest.body
    assert run(db)["errors"] == 0
    assert Feed.calls == 1
    assert logged.post("/discovery/refresh").status_code == 202
    assert run(db)["errors"] == 0
    assert Feed.calls == 2
    assert db.scalar(select(func.count()).select_from(Notification)) == count
    assert db.scalar(select(DiscoveryState)).summary["added"] == 0
    assert logged.get("/discovery").json()["summary"]["live_opportunities"] == 1


def test_pause_resume_and_source_disable_are_respected(db, user, logged):
    assert logged.put("/discovery", json={"enabled": False}).status_code == 200
    Feed.calls = 0
    run(db)
    assert Feed.calls == 0
    assert logged.post("/discovery/refresh").status_code == 409
    assert logged.put("/discovery", json={"enabled": True}).status_code == 200
    run(db)
    source = db.scalar(select(Source).where(Source.kind == "greenhouse"))
    assert logged.patch(f"/sources/{source.id}/toggle").status_code == 200
    logged.post("/discovery/refresh")
    run(db)
    assert Feed.calls == 1


def test_partial_source_failure_keeps_results_and_retries(db, user):
    bad = {**BOARD, "board": "broken", "company_name": "Unavailable"}
    assert run(db, (bad, BOARD))["errors"] == 1
    state = db.scalar(select(DiscoveryState))
    assert state.status == "DEGRADED"
    assert state.summary["added"] == 1
    assert state.next_run < utcnow() + timedelta(hours=2)
    assert db.scalar(select(SourceRun).where(SourceRun.status == "FAILED"))


def test_existing_board_is_not_duplicated_or_reconfigured(db, user):
    source = Source(
        user_id=user.id,
        name="My existing board",
        kind="greenhouse",
        enabled=False,
        config={"board": "fixture", "country": "India"},
    )
    db.add(source)
    db.commit()
    Feed.calls = 0
    run(db)
    assert Feed.calls == 0
    assert (
        db.scalar(select(func.count()).select_from(Source).where(Source.kind == "greenhouse")) == 1
    )
    db.refresh(source)
    assert source.name == "My existing board"
    assert source.config == {"board": "fixture", "country": "India"}


def test_overlapping_discovery_and_crash_recovery(db, user):
    Feed.calls = 0
    with job_lock(db.bind, f"discovery:{user.id}") as acquired:
        assert acquired
        run(db)
    assert Feed.calls == 0
    state = discovery.ensure_state(db, user.id)
    state.status, state.next_run = "RUNNING", None
    db.commit()
    assert run(db)["errors"] == 0
    assert Feed.calls == 1


def test_discovery_settings_are_private(db, user, logged):
    logged.put("/discovery", json={"enabled": False})
    logged.post("/auth/logout")
    logged.post(
        "/auth/register",
        json={
            "email": "other-discovery@example.com",
            "password": "Other-password-12345",
            "name": "Other",
        },
    )
    result = logged.get("/discovery")
    assert result.status_code == 200
    assert result.json()["enabled"] is True
    assert result.json()["summary"] == {}


def test_filter_keeps_technical_early_careers_without_guessing_remote_country():
    for title in [
        "SDE Intern - Frontend",
        "Junior Backend Developer",
        "Graduate Software Engineer",
        "Quality Assurance Engineering (QAE) - Intern",
    ]:
        assert early_career(JobIn(company_name="Example", title=title))
    for title in ["Senior Software Engineer", "International Sales Manager", "HR Intern"]:
        assert not early_career(JobIn(company_name="Example", title=title))
    assert (
        enrich_location(
            JobIn(company_name="Example", title="AI Intern", locations=["Remote"])
        ).country
        == "Unknown"
    )
