from collections import defaultdict
from datetime import datetime

from careeros.db import utcnow
from careeros.schemas import DEFAULT_WEIGHTS
from careeros.services.eligibility import evaluate

ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "postgres": "postgresql",
    "react.js": "react",
    "node.js": "nodejs",
    "node": "nodejs",
    "cpp": "c++",
    "amazon web services": "aws",
    "automated testing": "testing",
}


def skill_key(s):
    s = s.strip().casefold()
    return ALIASES.get(s, s)


def match(profile, job, skills, projects, preferences, now=None):
    now = now or utcnow()
    eligibility = evaluate(profile, job, now)
    known = {
        skill_key(s["name"])
        for s in skills
        if s.get("proficiency", 0) > 0 and s.get("learning_status") != "NOT_STARTED"
    }
    required = {skill_key(s) for s in job.get("required_skills", [])}
    preferred = {skill_key(s) for s in job.get("preferred_skills", [])} - required
    evidence = {skill_key(s) for p in projects for s in p.get("verified_skills", [])} & known
    missing = sorted(required - known)
    preferred_missing = sorted(preferred - known)
    all_skills = required | preferred
    denominator = len(required) * 2 + len(preferred)
    r = job.get("requirements", {})
    deadline = job.get("application_deadline")
    if isinstance(deadline, str):
        deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00")).replace(tzinfo=None)
    days = (deadline - now).total_seconds() / 86400 if deadline else None
    roles = [x.casefold() for x in preferences.get("target_roles", [])]
    countries = preferences.get("countries", [])
    factors = {
        "skill_fit": (len(required & known) * 2 + len(preferred & known)) / denominator
        if denominator
        else 0.5,
        "role_preference": 1.0 if job.get("normalized_role", "").casefold() in roles else 0,
        "project_evidence": len(all_skills & evidence) / len(all_skills) if all_skills else 0,
        "graduation_fit": 1.0
        if any(
            r.get(k)
            for k in ("allowed_graduation_years", "graduation_year_min", "graduation_year_max")
        )
        and not any("graduat" in reason.lower() for reason in eligibility["reasons"])
        else 0.5,
        "location_preference": 1.0
        if countries and job.get("country") == countries[0]
        else 0.7
        if job.get("country") in countries
        else 0,
        "experience_fit": 1.0
        if r.get("minimum_experience") is not None
        and profile.get("experience_years", 0) >= r["minimum_experience"]
        else 0.5
        if r.get("minimum_experience") is None
        else 0,
        "company_preference": 1.0
        if job.get("company_name", "").casefold()
        in [x.casefold() for x in preferences.get("preferred_companies", [])]
        else 0.5,
        "urgency": 1.0
        if days is not None and 0 < days <= 7
        else 0.5
        if days is not None and days > 7
        else 0,
    }
    weights = preferences.get("weights", DEFAULT_WEIGHTS)
    breakdown = {
        key: {
            "weight": weights[key],
            "fit": round(value, 3),
            "points": round(weights[key] * value, 2),
        }
        for key, value in factors.items()
    }
    score = round(sum(v["points"] for v in breakdown.values()))
    blocked = eligibility["state"] in ("NOT_ELIGIBLE", "CLOSED")
    if blocked:
        score, classification = 0, "LOW_PRIORITY"
    elif eligibility["state"] == "REVIEW_REQUIRED":
        classification = "WATCH"
    elif score >= 65 and not missing:
        classification = "APPLY_NOW"
    elif score >= 45 and missing:
        classification = "PREP_THEN_APPLY"
    elif score >= 35:
        classification = "WATCH"
    else:
        classification = "LOW_PRIORITY"
    return {
        "score": score,
        "classification": classification,
        "eligibility": eligibility,
        "strong_matches": sorted(all_skills & known),
        "missing_required": missing,
        "missing_preferred": preferred_missing,
        "project_evidence": sorted(all_skills & evidence),
        "preparation": [
            f"Practice {s} and be able to explain a project example" for s in missing[:5]
        ],
        "breakdown": breakdown,
        "score_suppressed": blocked,
        "algorithm_version": "1.0",
    }


EFFORT_HOURS = {
    "docker": 12,
    "aws": 24,
    "testing": 16,
    "kubernetes": 50,
    "sql": 20,
    "python": 30,
    "typescript": 20,
}


def skill_gaps(ranked_jobs):
    scores = defaultdict(lambda: {"jobs": 0, "required_count": 0, "weighted_demand": 0.0})
    for job in ranked_jobs:
        m = job["match"]
        if (
            m["eligibility"]["state"] in ("NOT_ELIGIBLE", "CLOSED")
            or m["score"] < 35
            or m["breakdown"]["role_preference"]["fit"] == 0
        ):
            continue
        for required, values in [(True, m["missing_required"]), (False, m["missing_preferred"])]:
            for skill in values:
                item = scores[skill]
                item["jobs"] += 1
                item["required_count"] += int(required)
                item["weighted_demand"] += (2 if required else 1) * m["score"] / 100
    result = []
    for skill, values in scores.items():
        hours = EFFORT_HOURS.get(skill, 24)
        result.append(
            {
                "skill": skill,
                **values,
                "estimated_hours": hours,
                "priority": round(values["weighted_demand"] / hours * 100, 2),
                "explanation": "Required skills count twice; demand is weighted by job match and divided by estimated learning hours. Estimates are planning heuristics.",
            }
        )
    return sorted(result, key=lambda item: (-item["priority"], item["skill"]))
