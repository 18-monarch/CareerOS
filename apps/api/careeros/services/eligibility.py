"""Pure deterministic rules. Unknown or machine-extracted hard facts never become hard passes."""

import re
from datetime import datetime

from careeros.db import utcnow


def normalized(value):
    text = re.sub(r"[^a-z0-9]", "", (value or "").lower())
    aliases = {
        "btech": "bachelor",
        "be": "bachelor",
        "bacheloroftechnology": "bachelor",
        "bachelorofengineering": "bachelor",
        "bs": "bachelor",
        "cse": "computerscience",
        "cs": "computerscience",
        "computerscienceengineering": "computerscience",
        "computerscienceandengineering": "computerscience",
    }
    return aliases.get(text, text)


def evaluate(profile: dict, job: dict, now: datetime | None = None):
    now = now or utcnow()
    r = job.get("requirements", {})
    provenance = job.get("provenance", {})
    failures, reviews, passes = [], [], []
    for key in ("application_deadline", "expires_at"):
        value = job.get(key)
        if isinstance(value, str):
            from datetime import UTC

            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if value.tzinfo:
                value = value.astimezone(UTC).replace(tzinfo=None)
        if value and value <= now:
            return {
                "state": "CLOSED",
                "reasons": [f"{key.replace('_', ' ').capitalize()} has passed"],
                "checks": [],
            }
    if not job.get("is_active", True):
        return {
            "state": "CLOSED",
            "reasons": ["Source marks this opportunity inactive"],
            "checks": [],
        }

    def check(field, passed, message, known=True):
        info = provenance.get(field, {})
        uncertain = info.get("method") in ("rules", "ai") and not info.get("confirmed", False)
        if uncertain:
            reviews.append(f"Verify extracted requirement: {message}")
        elif not known:
            reviews.append(f"Profile information missing: {message}")
        elif passed:
            passes.append(message)
        else:
            failures.append(message)

    year = profile.get("graduation_year")
    for field, ok, detail in [
        (
            "allowed_graduation_years",
            year in r.get("allowed_graduation_years", []),
            f"Allowed graduation years: {r.get('allowed_graduation_years')}; yours: {year}",
        ),
        (
            "graduation_year_min",
            year is not None and year >= (r.get("graduation_year_min") or 0),
            f"Graduate no earlier than {r.get('graduation_year_min')}; yours: {year}",
        ),
        (
            "graduation_year_max",
            year is not None and year <= (r.get("graduation_year_max") or 9999),
            f"Graduate no later than {r.get('graduation_year_max')}; yours: {year}",
        ),
    ]:
        if r.get(field):
            check(field, ok, detail, year is not None)
    if r.get("minimum_cgpa") is not None:
        cgpa = profile.get("cgpa")
        check(
            "minimum_cgpa",
            cgpa is not None and cgpa >= r["minimum_cgpa"],
            f"Minimum CGPA: {r['minimum_cgpa']}; yours: {cgpa}",
            cgpa is not None,
        )
    for field, candidate in [
        ("degree_requirements", profile.get("degree")),
        ("branch_requirements", profile.get("branch")),
    ]:
        if r.get(field):
            check(
                field,
                normalized(candidate) in [normalized(x) for x in r[field]],
                f"Required {field.split('_')[0]}: {', '.join(r[field])}; yours: {candidate or 'unknown'}",
                bool(candidate),
            )
    experience = profile.get("experience_years")
    for field, ok in [
        (
            "minimum_experience",
            experience is not None and experience >= (r.get("minimum_experience") or 0),
        ),
        (
            "maximum_experience",
            experience is not None and experience <= (r.get("maximum_experience") or 0),
        ),
    ]:
        if r.get(field) is not None:
            check(
                field,
                ok,
                f"{field.replace('_', ' ').capitalize()}: {r[field]} years; yours: {experience}",
                experience is not None,
            )
    authorizations = [x.casefold() for x in profile.get("work_authorizations", [])]
    auth = r.get("work_authorization")
    if auth:
        check(
            "work_authorization",
            auth.casefold() in authorizations,
            f"Requires existing work authorization: {auth}",
        )
    country = job.get("country", "Unknown")
    if not auth and country.casefold() not in authorizations:
        if r.get("international_candidates_allowed") is False:
            check(
                "international_candidates_allowed",
                False,
                "International candidates explicitly excluded; local authorization not recorded",
            )
        else:
            reviews.append(
                f"Confirm work authorization and sponsorship for {country}; a job match is not visa eligibility"
            )
    if r.get("language_requirement"):
        reviews.append(f"Confirm language requirement: {r['language_requirement']}")
    if failures:
        state, reasons = "NOT_ELIGIBLE", failures + reviews
    elif reviews:
        state, reasons = "REVIEW_REQUIRED", reviews
    elif not passes:
        state, reasons = (
            "LIKELY_ELIGIBLE",
            ["No disqualifying structured requirements found; confirm the original posting"],
        )
    else:
        state, reasons = (
            "ELIGIBLE",
            ["All published structured hard requirements checked against your profile"],
        )
    return {"state": state, "reasons": reasons, "checks": passes}
