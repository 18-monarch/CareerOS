from copy import deepcopy
from datetime import datetime, timedelta

import pytest
from careeros.schemas import JobIn, PreferenceIn, ProfileIn
from careeros.services.eligibility import evaluate
from careeros.services.matching import match, skill_gaps
from careeros.services.parsing import parse_notice
from careeros.services.repository import identity, normalized_url

PROFILE = {
    "graduation_year": 2028,
    "cgpa": 7.38,
    "degree": "B.Tech",
    "branch": "CSE",
    "experience_years": 0,
    "work_authorizations": ["India"],
}
JOB = {
    "title": "Software Engineer Intern",
    "company_name": "Example",
    "country": "India",
    "normalized_role": "Software Engineer",
    "requirements": {"minimum_cgpa": 7, "allowed_graduation_years": [2028]},
    "required_skills": ["Python"],
    "preferred_skills": ["Docker"],
    "is_active": True,
}


@pytest.mark.parametrize(
    "requirements,state",
    [
        ({"minimum_cgpa": 8}, "NOT_ELIGIBLE"),
        ({"minimum_cgpa": 7.38}, "ELIGIBLE"),
        ({"allowed_graduation_years": [2027]}, "NOT_ELIGIBLE"),
        ({"graduation_year_min": 2029}, "NOT_ELIGIBLE"),
        ({"graduation_year_max": 2027}, "NOT_ELIGIBLE"),
        ({"degree_requirements": ["B.E."]}, "ELIGIBLE"),
        ({"degree_requirements": ["M.Tech"]}, "NOT_ELIGIBLE"),
        ({"branch_requirements": ["Computer Science and Engineering"]}, "ELIGIBLE"),
        ({"minimum_experience": 2}, "NOT_ELIGIBLE"),
        ({"work_authorization": "USA"}, "NOT_ELIGIBLE"),
        ({}, "LIKELY_ELIGIBLE"),
    ],
)
def test_hard_rules(requirements, state):
    assert evaluate(PROFILE, {**JOB, "requirements": requirements})["state"] == state


def test_unknowns_and_extracted_facts_require_review():
    assert evaluate({**PROFILE, "cgpa": None}, JOB)["state"] == "REVIEW_REQUIRED"
    job = {
        **JOB,
        "requirements": {"minimum_cgpa": 8},
        "provenance": {"minimum_cgpa": {"method": "ai", "confidence": 0.99}},
    }
    assert evaluate(PROFILE, job)["state"] == "REVIEW_REQUIRED"
    job["provenance"]["minimum_cgpa"]["confirmed"] = True
    assert evaluate(PROFILE, job)["state"] == "NOT_ELIGIBLE"
    assert evaluate(PROFILE, {**JOB, "country": "Germany"})["state"] == "REVIEW_REQUIRED"


def test_deadlines_are_hard_boundaries():
    now = datetime(2026, 10, 6)
    assert evaluate(PROFILE, {**JOB, "application_deadline": now}, now)["state"] == "CLOSED"
    assert (
        evaluate(PROFILE, {**JOB, "expires_at": now - timedelta(seconds=1)}, now)["state"]
        == "CLOSED"
    )
    assert evaluate(PROFILE, {**JOB, "is_active": False}, now)["state"] == "CLOSED"


def test_preferred_skill_does_not_disqualify_and_score_explained():
    result = match(
        PROFILE, JOB, [{"name": "Python", "proficiency": 3}], [], PreferenceIn().model_dump()
    )
    assert result["eligibility"]["state"] == "ELIGIBLE"
    assert result["missing_preferred"] == ["docker"]
    assert result["missing_required"] == []
    assert result["score"] == round(sum(x["points"] for x in result["breakdown"].values()))
    assert result == match(
        PROFILE,
        deepcopy(JOB),
        [{"name": "Python", "proficiency": 3}],
        [],
        PreferenceIn().model_dump(),
    )


def test_blocked_jobs_cannot_be_recommended():
    result = match(
        PROFILE,
        {**JOB, "requirements": {"minimum_cgpa": 8}},
        [{"name": "Python", "proficiency": 5}],
        [{"verified_skills": ["Python"]}],
        PreferenceIn().model_dump(),
    )
    assert result["score"] == 0
    assert result["classification"] == "LOW_PRIORITY"


def test_project_technologies_are_not_proof():
    result = match(
        PROFILE,
        JOB,
        [{"name": "Python", "proficiency": 1}],
        [{"technologies": ["Python"], "verified_skills": []}],
        PreferenceIn().model_dump(),
    )
    assert result["project_evidence"] == []


def test_skill_gap_ignores_blocked_and_weights_effort():
    rows = []
    for preferred in (["Docker"], ["Docker"], ["Kubernetes"]):
        job = {**JOB, "preferred_skills": preferred}
        rows.append(
            {
                **job,
                "match": match(
                    PROFILE,
                    job,
                    [{"name": "Python", "proficiency": 3}],
                    [],
                    PreferenceIn().model_dump(),
                ),
            }
        )
    bad = {**JOB, "requirements": {"minimum_cgpa": 9}, "preferred_skills": ["Redis"]}
    rows.append({**bad, "match": match(PROFILE, bad, [], [], PreferenceIn().model_dump())})
    gaps = skill_gaps(rows)
    assert gaps[0]["skill"] == "docker" and gaps[0]["jobs"] == 2
    assert not any(g["skill"] == "redis" for g in gaps)


def test_identity_normalizes_tracking_but_preserves_requisition():
    a = {**JOB, "application_url": "https://example.com/job/1?utm_source=a"}
    b = {**a, "application_url": "https://example.com/job/1?utm_source=b#apply"}
    assert identity(a) == identity(b)
    assert identity({**a, "requisition_id": "one"}) != identity({**a, "requisition_id": "two"})
    assert (
        normalized_url("https://example.com/jobs?gh_jid=2&utm_medium=x")
        == "https://example.com/jobs?gh_jid=2"
    )


def test_parser_preserves_evidence_and_preferred_skills():
    result = parse_notice(
        "Company: Acme\nRole: Software Engineer Intern\nCGPA: 8.0\nBatch: 2028\nBranches: CSE\nRequired: Python, SQL\nPreferred: Docker\nDeadline: 2027-01-20\nLocation: Ahmedabad\nStipend: INR 30000\nSelection stages: OA, Interview"
    )
    job = result["job"]
    assert job["requirements"]["minimum_cgpa"] == 8
    assert job["requirements"]["allowed_graduation_years"] == [2028]
    assert "Docker" not in job["required_skills"] and "Docker" in job["preferred_skills"]
    assert job["provenance"]["minimum_cgpa"]["source_text"] == "CGPA: 8.0"
    assert result["warnings"]
    assert job["selection_stages"] == ["OA", "Interview"]


def test_validation_blocks_unsafe_urls_and_weights():
    with pytest.raises(ValueError):
        JobIn(company_name="A", title="Role", application_url="javascript:alert(1)")
    with pytest.raises(ValueError):
        PreferenceIn(weights={"skill_fit": 100})
    with pytest.raises(ValueError):
        ProfileIn(name="A", external_profiles={"github": "data:hello"})
