from datetime import timedelta

from careeros.db import utcnow
from careeros.models import ApplicationEvent, AuthSession, Job
from sqlalchemy import select


def test_auth_cookie_rotation_csrf_and_logout(client):
    body = {"email": "new@example.com", "password": "Secure-password-123", "name": "New User"}
    response = client.post("/auth/register", json=body)
    assert response.status_code == 201
    assert "HttpOnly" in response.headers.get_list("set-cookie")[0]
    assert client.get("/auth/me").json()["name"] == "New User"
    assert client.put("/profile", json={"name": "No CSRF"}).status_code == 403
    client.headers["x-csrf-token"] = response.json()["csrf_token"]
    old = client.cookies.get("career_refresh")
    refresh = client.post("/auth/refresh")
    assert refresh.status_code == 200
    assert client.cookies.get("career_refresh") != old
    client.headers["x-csrf-token"] = refresh.json()["csrf_token"]
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401
    assert (
        client.post("/auth/login", json={**body, "password": "Wrong-password-123"}).status_code
        == 401
    )


def test_invalid_origin_and_unknown_access(client):
    assert client.get("/jobs").status_code == 401
    assert (
        client.post(
            "/auth/login",
            json={"email": "n@example.com", "password": "Long-password-123"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )


def test_sensitive_rate_limit(client):
    for _ in range(10):
        assert (
            client.post(
                "/auth/login", json={"email": "nope@example.com", "password": "Wrong-password-123"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/auth/login", json={"email": "nope@example.com", "password": "Wrong-password-123"}
        ).status_code
        == 429
    )


def test_core_workflow_persistence_and_history(logged, db):
    c = logged
    profile = c.get("/profile").json()
    assert profile["cgpa"] == 7.38 and profile["graduation_year"] == 2028
    profile.pop("email")
    profile["semester"] = 6
    assert c.put("/profile", json=profile).status_code == 200
    assert c.get("/profile").json()["semester"] == 6
    jobs = c.get("/jobs").json()
    assert jobs["total"] == 8
    job = jobs["items"][0]
    detail = c.get(f"/jobs/{job['id']}").json()
    assert detail["match"]["eligibility"]["state"] == "ELIGIBLE"
    assert detail["match"]["breakdown"] and detail["match"]["missing_preferred"]
    saved = c.post("/applications", json={"job_id": job["id"], "status": "SAVED"})
    assert saved.status_code == 201, saved.text
    id = saved.json()["id"]
    for state in ["APPLIED", "OA_RECEIVED", "OA_COMPLETED", "INTERVIEW", "REJECTED"]:
        r = c.patch(
            f"/applications/{id}", json={"job_id": job["id"], "status": state, "notes": state}
        )
        assert r.status_code == 200, r.text
    assert len(c.get(f"/applications/{id}/events").json()) == 6
    assert db.scalar(
        select(ApplicationEvent).where(
            ApplicationEvent.application_id == id, ApplicationEvent.status == "APPLIED"
        )
    )
    metrics = c.get("/applications/metrics").json()
    assert metrics["counts"]["APPLIED"] == 1 and metrics["counts"]["INTERVIEW"] == 1
    assert metrics["rates"]["oa_pass_rate"] == 100
    assert "Too little" in metrics["recommendation"]
    dashboard = c.get("/dashboard").json()
    assert dashboard["pipeline"]["counts"]["APPLIED"] == 1
    dashboard_job = next(j for j in dashboard["top_jobs"] if j["id"] == job["id"])
    assert dashboard_job["application"] == {"id": id, "status": "REJECTED"}
    assert not dashboard["next_deadline"] or dashboard["next_deadline"]["id"] != job["id"]
    assert c.get("/learning/recommendations").json()[0]["skill"] == "docker"
    assert c.post("/notifications/generate").status_code == 200
    before = len(c.get("/notifications").json())
    assert c.post("/notifications/generate").json()["created"] == 0
    assert len(c.get("/notifications").json()) == before
    db.expire_all()
    assert db.get(Job, job["id"]).title == job["title"]


def test_manual_dedup_and_campus_eligibility(logged):
    text = "Company: Campus Firm\nRole: Software Engineer Intern\nCGPA: 8.0\nBatch: 2028\nRequired: Python\nPreferred: Docker"
    parsed = logged.post("/campus/parse", json={"text": text}).json()["job"]
    parsed["country"] = "India"
    parsed["provenance"] = {k: {**v, "confirmed": True} for k, v in parsed["provenance"].items()}
    a = logged.post("/campus/jobs", json=parsed)
    b = logged.post("/campus/jobs", json=parsed)
    assert a.status_code == 201 and b.status_code == 201
    assert a.json()["id"] == b.json()["id"]
    assert b.json()["created"] is False
    assert logged.get(f"/jobs/{a.json()['id']}/eligibility").json()["state"] == "NOT_ELIGIBLE"


def test_filters_and_pagination(logged):
    first = logged.get("/jobs?page_size=2").json()
    second = logged.get("/jobs?page_size=2&page=2").json()
    assert len(first["items"]) == 2 and not set(j["id"] for j in first["items"]) & set(
        j["id"] for j in second["items"]
    )
    assert logged.get("/jobs?eligibility=NOT_ELIGIBLE").json()["total"] == 3
    assert logged.get("/jobs?country=Netherlands").json()["total"] == 1
    assert logged.get("/jobs?page_size=999").status_code == 422


def test_tenant_isolation(logged, client, db, user):
    id = logged.get("/jobs").json()["items"][0]["id"]
    app_id = logged.post("/applications", json={"job_id": id}).json()["id"]
    other = client.post(
        "/auth/register",
        json={"name": "Other", "email": "other@example.com", "password": "Other-password-123"},
    )
    client.headers["x-csrf-token"] = other.json()["csrf_token"]
    assert client.get("/jobs").json()["total"] == 0
    assert client.get(f"/jobs/{id}").status_code == 404
    assert client.get(f"/applications/{app_id}/events").status_code == 404
    assert client.post("/applications", json={"job_id": id}).status_code == 404
    assert client.patch(f"/applications/{app_id}", json={"job_id": id}).status_code == 404


def test_other_modules_persist(logged):
    assert (
        logged.post(
            "/skills", json={"name": "Docker", "category": "DevOps", "proficiency": 2}
        ).status_code
        == 201
    )
    assert any(s["name"] == "docker" for s in logged.get("/skills").json())
    p = logged.post(
        "/projects", json={"name": "Real project", "verified_skills": ["Docker"]}
    ).json()
    assert (
        logged.put(
            f"/projects/{p['id']}/mastery", json={"topic": "Architecture", "status": "COMFORTABLE"}
        ).status_code
        == 200
    )
    assert any(x["mastery"] for x in logged.get("/projects").json() if x["id"] == p["id"])
    assert (
        logged.post(
            "/dsa", json={"topic": "Arrays", "problem": "Two Sum", "independent": True}
        ).status_code
        == 201
    )
    assert logged.get("/dsa").json()["topics"][0]["independent"] == 1
    assert (
        logged.put("/learning/progress", json={"topic": "docker", "status": "LEARNING"}).status_code
        == 200
    )
    assert (
        logged.post(
            "/market-reports",
            json={
                "market": "India",
                "period": "2026-10",
                "source_references": ["https://example.com/report"],
                "software_hiring_trend": "Manually recorded test observation",
            },
        ).status_code
        == 201
    )
    assert (
        logged.post(
            "/visa-rules",
            json={
                "country": "Germany",
                "last_verified": "2025-01-01T00:00:00",
                "source_url": "https://example.com/official",
            },
        ).status_code
        == 201
    )
    assert logged.get("/visa-rules").json()[0]["stale"] is True
    assert logged.post("/resumes", json={"name": "Master", "is_master": True}).status_code == 201
    assert logged.get("/resumes").json()[0]["is_master"]


def test_expired_access_denied_but_refresh_works(logged, db):
    session = db.scalar(select(AuthSession))
    session.access_expires = utcnow() - timedelta(seconds=1)
    db.commit()
    assert logged.get("/profile").status_code == 401
    response = logged.post("/auth/refresh")
    assert response.status_code == 200
    logged.headers["x-csrf-token"] = response.json()["csrf_token"]
    assert logged.get("/profile").status_code == 200


def test_job_corrections_keep_identity_and_original_evidence(logged, db):
    id = logged.get("/jobs").json()["items"][0]["id"]
    detail = logged.get(f"/jobs/{id}").json()
    correction = {
        "company_name": detail["company_name"],
        "title": detail["title"],
        "country": "India",
        "requirements": {"minimum_cgpa": 8},
        "provenance": {"minimum_cgpa": {"method": "manual", "confirmed": True}},
        "required_skills": ["Python"],
    }
    response = logged.put(f"/jobs/{id}", json=correction)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == id
    assert response.json()["human_reviewed"]
    assert logged.get(f"/jobs/{id}/eligibility").json()["state"] == "NOT_ELIGIBLE"
    assert logged.get(f"/jobs/{id}").json()["occurrences"]
