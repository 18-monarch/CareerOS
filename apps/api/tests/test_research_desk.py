import asyncio
import base64
import hashlib
from types import SimpleNamespace
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from careeros.apply_runner import process
from careeros.db import build_engine
from careeros.models import Job, Preferences, ResumeVersion
from careeros.services.application_desk import approve, can_auto_approve, prepare
from careeros.services.categories import classify
from careeros.services.research import ats_reference, record_lead, run_research, verify_lead
from careeros.services.startup import migrate_local, schema_revision
from sqlalchemy import select, text

PDF = b"%PDF-1.4\nfixture resume\n%%EOF"


def verifier_for(job):
    async def verify(url):
        return job, {}, "VERIFIED_LISTING", "Fixture live check"

    return verify


def live_job(db, user, design=False):
    job = db.scalar(select(Job).where(Job.user_id == user.id).limit(1))
    job.is_demo = False
    job.is_active = True
    job.country = "India"
    job.title = "Product Design Intern" if design else "Backend Software Intern"
    job.application_deadline = None
    job.expires_at = None
    job.application_url = "https://jobs.lever.co/fixture/12345678-1234-1234-1234-123456789012/apply"
    job.requirements.data = {}
    job.requirements.provenance = {}
    db.commit()
    return job


def configure_resume(db, user):
    resume = ResumeVersion(
        user_id=user.id,
        name="Software resume",
        data={
            "sha256": hashlib.sha256(PDF).hexdigest(),
            "content_base64": base64.b64encode(PDF).decode(),
            "file_name": "resume.pdf",
        },
    )
    db.add(resume)
    db.flush()
    pref = db.scalar(select(Preferences).where(Preferences.user_id == user.id))
    pref.data = {
        **pref.data,
        "application_settings": {
            "software_resume_id": resume.id,
            "design_resume_id": resume.id,
            "daily_limit": 1,
        },
    }
    db.commit()
    return resume


def test_design_categories_and_filter(logged, db, user):
    job = live_job(db, user, True)
    assert classify("Product Design Intern") == ["design"]
    assert "ux_research" in classify("UX Research Intern")
    assert "design_engineering" not in classify("Mechanical Design Engineer Intern")
    result = logged.get("/jobs?category=design").json()
    assert [j["id"] for j in result["items"]] == [job.id]
    brief = logged.get("/research").json()
    assert brief["search_configured"] is False
    assert next(g for g in brief["groups"] if g["id"] == "design")["items"][0]["id"] == job.id


def test_research_rejects_private_or_unrecognized_fetch_targets():
    for url in [
        "http://127.0.0.1/a",
        "https://localhost/a",
        "https://jobs.lever.co.evil.com/x/y",
        "https://jobs.lever.co@127.0.0.1/x/y",
        "https://jobs.lever.co:8443/x/y",
        "https://jobs.lever.co/../secret",
    ]:
        try:
            assert ats_reference(url) is None
        except ValueError:
            pass


def test_lead_verification_dedupe_and_dismissal(db, user):
    url = "https://job-boards.greenhouse.io/project44/jobs/8101750"
    lead = record_lead(db, user.id, url, title="From search")
    raw = {
        "id": 8101750,
        "title": "Product Design Intern",
        "content": "Figma and prototyping. Graduation: 2028",
        "location": {"name": "Bengaluru, India"},
        "absolute_url": url,
    }
    with patch("careeros.services.research.fetch_json", return_value=raw):
        asyncio.run(verify_lead(db, lead))
        assert lead.status == "VERIFIED_LISTING"
        job_id = lead.data["job_id"]
        asyncio.run(verify_lead(db, lead))
        assert lead.data["job_id"] == job_id and lead.data["added"] is False
    job = db.get(Job, job_id)
    assert job.country == "India"
    assert job.requirements.provenance["allowed_graduation_years"].get("confirmed", False) is False
    assert job.data["listing_verification"]["method"] == "public_ats"
    lead.status = "DISMISSED"
    db.commit()
    with patch("careeros.services.research.verify_posting") as fetch:
        asyncio.run(verify_lead(db, lead))
        fetch.assert_not_called()
    assert record_lead(db, user.id, url, title="Seen again").id == lead.id


def test_research_search_errors_are_explicit(db, user):
    settings = SimpleNamespace(
        brave_search_api_key="test", research_query_limit=2, research_result_limit=3
    )
    with (
        patch("careeros.services.research.get_settings", return_value=settings),
        patch("careeros.services.research.web_search", side_effect=ValueError("bad search")),
    ):
        result = asyncio.run(run_research(db, user))
    assert result["status"] == "FAILED" and result["errors"] == 2


def test_unsupported_lead_never_becomes_verified(db, user):
    lead = record_lead(db, user.id, "https://example.com/jobs/intern", title="2028 eligible")
    asyncio.run(verify_lead(db, lead))
    assert lead.status == "REVIEW_REQUIRED" and "job_id" not in lead.data


def test_pdf_upload_metadata_and_draft_api(logged, db, user):
    job = live_job(db, user)
    rid = logged.post("/resumes", json={"name": "Software"}).json()["id"]
    assert (
        logged.put(
            f"/resumes/{rid}/pdf", json={"content_base64": base64.b64encode(b"not a pdf").decode()}
        ).status_code
        == 422
    )
    assert (
        logged.put(
            f"/resumes/{rid}/pdf", json={"content_base64": base64.b64encode(PDF).decode()}
        ).status_code
        == 200
    )
    assert logged.put(f"/resumes/{rid}", json={"name": "Software revised"}).status_code == 200
    metadata = next(r for r in logged.get("/resumes").json() if r["id"] == rid)
    assert metadata["sha256"] and "content_base64" not in metadata
    assert logged.put("/application-settings", json={"software_resume_id": rid}).status_code == 200
    d = logged.post("/application-desk/prepare", json={"job_id": job.id}).json()
    assert d["status"] == "DRAFT" and d["packet"]["email"] == user.email
    assert (
        logged.post(f"/application-desk/{d['id']}/approve", json={"reviewed": False}).status_code
        == 422
    )
    assert (
        logged.post(f"/application-desk/{d['id']}/approve", json={"reviewed": True}).status_code
        == 200
    )
    assert (
        logged.put(f"/application-desk/{d['id']}", json={"cover_letter": "changed"}).status_code
        == 409
    )


def test_changed_resume_invalidates_approval(db, user):
    job = live_job(db, user)
    resume = configure_resume(db, user)
    d = prepare(db, user, job)
    approve(db, user, d, True)
    resume.data = {**resume.data, "sha256": "changed"}
    db.commit()
    with patch("subprocess.run") as browser:
        process(db, user, submit=True)
        browser.assert_not_called()
    assert d.status == "HANDOFF" and "changed" in d.data["result"]["reason"]


def test_submission_confirmation_recorded_once(db, user):
    job = live_job(db, user)
    configure_resume(db, user)
    d = prepare(db, user, job)
    approve(db, user, d, True)
    calls = []

    def browser(payload):
        calls.append(payload)
        return {
            "status": "SUBMITTED",
            "reason": "Fixture confirmation",
            "confirmation": "Thank you for applying",
        }

    result = process(db, user, submit=True, executor=browser, verifier=verifier_for(job))
    assert result[0]["status"] == "SUBMITTED" and d.status == "SUBMITTED"
    assert process(db, user, submit=True, executor=browser, verifier=verifier_for(job)) == []
    assert len(calls) == 1
    from careeros.models import Application

    app = db.scalar(
        select(Application).where(Application.user_id == user.id, Application.job_id == job.id)
    )
    assert app.status == "APPLIED" and app.applied_at


def test_unknown_submission_is_never_retried(db, user):
    job = live_job(db, user)
    configure_resume(db, user)
    d = prepare(db, user, job)
    approve(db, user, d, True)
    process(
        db,
        user,
        True,
        executor=lambda payload: {"status": "UNCERTAIN", "reason": "No confirmation"},
        verifier=verifier_for(job),
    )
    assert d.status == "UNCERTAIN"
    assert process(db, user, True, executor=lambda payload: 1 / 0) == []


def test_design_requires_portfolio_and_auto_mode_is_conservative(db, user):
    job = live_job(db, user, True)
    configure_resume(db, user)
    d = prepare(db, user, job)
    assert any("portfolio" in b for b in d.data["blockers"])
    assert not can_auto_approve(db, user, d)


def test_cross_account_draft_and_resume_protected(logged, client, db, user):
    job = live_job(db, user)
    resume = configure_resume(db, user)
    d = prepare(db, user, job)
    client.post("/auth/logout")
    response = client.post(
        "/auth/register",
        json={"email": "other@example.com", "password": "Other-password-12345", "name": "Other"},
    )
    client.headers["x-csrf-token"] = response.json()["csrf_token"]
    assert (
        client.post(f"/application-desk/{d.id}/approve", json={"reviewed": True}).status_code == 404
    )
    assert (
        client.put(
            f"/resumes/{resume.id}/pdf", json={"content_base64": base64.b64encode(PDF).decode()}
        ).status_code
        == 404
    )
    assert client.get("/application-desk").json()["drafts"] == []


def test_local_upgrade_backs_up_and_preserves_old_database(tmp_path):
    from pathlib import Path

    dbpath = tmp_path / "old.db"
    url = f"sqlite:///{dbpath}"
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    with patch("careeros.config.get_settings", return_value=SimpleNamespace(database_url=url)):
        command.upgrade(config, "d82f04")
    engine = build_engine(url)
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users (id,name,email,password_hash,created_at,updated_at,is_admin) VALUES ('keep','Keep','keep@example.com','unused',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,0)"
            )
        )
    settings = SimpleNamespace(environment="development", auto_migrate_local=True)
    with patch("careeros.services.startup.get_settings", return_value=settings):
        migrate_local(engine)
        migrate_local(engine)
    assert schema_revision(engine) == "e91a05"
    assert len(list(tmp_path.glob("*.backup-*"))) == 1
    with engine.connect() as c:
        assert c.scalar(text("SELECT name FROM users")) == "Keep"
    engine.dispose()


def test_web_search_contract_and_query_rotation(db, user):
    import httpx
    from careeros.services import research

    settings = SimpleNamespace(
        brave_search_api_key="fixture-key", research_query_limit=2, research_result_limit=3
    )
    seen = []

    def upstream(request):
        assert request.url.host == "api.search.brave.com"
        assert request.headers["x-subscription-token"] == "fixture-key"
        seen.append(request.url.params["q"])
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "url": "https://example.com/intern",
                            "title": "Fixture search result",
                            "description": "An unverified snippet",
                        }
                    ]
                }
            },
        )

    factory = httpx.AsyncClient
    with (
        patch.object(research, "get_settings", return_value=settings),
        patch.object(
            research.httpx,
            "AsyncClient",
            side_effect=lambda **kwargs: factory(transport=httpx.MockTransport(upstream), **kwargs),
        ),
    ):
        first = asyncio.run(research.run_research(db, user))
        second = asyncio.run(research.run_research(db, user, first["next_query_offset"]))
    assert first["leads"] == 1 and second["leads"] == 1
    assert len(set(seen)) == 4
    from careeros.models import ResearchLead

    rows = list(db.scalars(select(ResearchLead).where(ResearchLead.user_id == user.id)))
    assert len(rows) == 1 and rows[0].status == "REVIEW_REQUIRED"


def test_research_posting_closure_is_not_a_network_failure(db, user):
    import httpx

    url = "https://job-boards.greenhouse.io/project44/jobs/8101750"
    raw = {
        "id": 8101750,
        "title": "Product Design Intern",
        "content": "Figma",
        "location": {"name": "India"},
        "absolute_url": url,
    }
    lead = record_lead(db, user.id, url)
    with patch("careeros.services.research.fetch_json", return_value=raw):
        asyncio.run(verify_lead(db, lead))
    job = db.get(Job, lead.data["job_id"])
    request = httpx.Request("GET", url)
    for code, active in [(503, True), (404, False)]:
        failure = httpx.HTTPStatusError(
            "fixture", request=request, response=httpx.Response(code, request=request)
        )
        with patch("careeros.services.research.fetch_json", side_effect=failure):
            asyncio.run(verify_lead(db, lead))
        assert job.is_active is active
    with patch("careeros.services.research.fetch_json", return_value=raw):
        asyncio.run(verify_lead(db, lead))
    assert job.is_active


def test_auto_approval_requires_every_saved_rule(db, user):
    job = live_job(db, user)
    configure_resume(db, user)
    job.data = {**job.data, "human_reviewed": True}
    job.requirements.data = {"minimum_experience": 0}
    prefs = db.scalar(select(Preferences).where(Preferences.user_id == user.id))
    cfg = {
        **prefs.data["application_settings"],
        "mode": "auto_submit",
        "companies": [job.company.name],
        "minimum_score": 0,
        "countries": ["India"],
    }
    prefs.data = {**prefs.data, "application_settings": cfg}
    db.commit()
    draft = prepare(db, user, job)
    assert draft.data["eligibility"]["state"] == "ELIGIBLE"
    assert can_auto_approve(db, user, draft)
    prefs.data = {**prefs.data, "application_settings": {**cfg, "companies": []}}
    db.commit()
    draft = prepare(db, user, job)
    assert not can_auto_approve(db, user, draft)


def test_live_pre_submission_change_prevents_browser_action(db, user):
    from types import SimpleNamespace

    job = live_job(db, user)
    configure_resume(db, user)
    draft = prepare(db, user, job)
    approve(db, user, draft, True)

    async def changed(url):
        return (
            SimpleNamespace(title=job.title, description="Changed requirements"),
            {},
            "VERIFIED_LISTING",
            "Found",
        )

    with patch("subprocess.run") as browser:
        process(db, user, submit=True, verifier=changed)
        browser.assert_not_called()
    assert draft.status == "HANDOFF"


def test_meaningful_alerts_dedupe_and_include_design(db, user):
    from careeros.services.notifications import meaningful_updates

    job = live_job(db, user, True)
    assert meaningful_updates(db, user) == 1
    assert meaningful_updates(db, user) == 0
    job.description += "\nNew deadline or requirement information."
    db.commit()
    assert meaningful_updates(db, user) == 1
