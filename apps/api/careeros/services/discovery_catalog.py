"""Public employer boards verified on 2026-10-08; no search/API credentials required."""

import re

from careeros.services.categories import classify

CATALOG = (
    {
        "kind": "greenhouse",
        "board": "project44",
        "company_name": "project44",
        "url": "https://job-boards.greenhouse.io/project44",
    },
    {
        "kind": "lever",
        "board": "hevodata",
        "company_name": "Hevo Data",
        "url": "https://jobs.lever.co/hevodata",
    },
    {
        "kind": "ashby",
        "board": "level-ai",
        "company_name": "Level AI",
        "url": "https://jobs.ashbyhq.com/level-ai",
    },
    {
        "kind": "ashby",
        "board": "niural",
        "company_name": "Niural",
        "url": "https://jobs.ashbyhq.com/niural",
    },
    {
        "kind": "greenhouse",
        "board": "enterpret",
        "company_name": "Enterpret",
        "url": "https://job-boards.greenhouse.io/enterpret",
    },
    {
        "kind": "greenhouse",
        "board": "cloudsek",
        "company_name": "CloudSEK",
        "url": "https://job-boards.greenhouse.io/cloudsek",
    },
    {
        "kind": "greenhouse",
        "board": "nirmata",
        "company_name": "Nirmata",
        "url": "https://job-boards.greenhouse.io/nirmata",
    },
    {
        "kind": "lever",
        "board": "drivetrain",
        "company_name": "Drivetrain",
        "url": "https://jobs.lever.co/drivetrain",
    },
    {
        "kind": "ashby",
        "board": "certifyos",
        "company_name": "CertifyOS",
        "url": "https://jobs.ashbyhq.com/certifyos",
    },
    {
        "kind": "greenhouse",
        "board": "headoutcareers",
        "company_name": "Headout",
        "url": "https://job-boards.greenhouse.io/headoutcareers",
    },
)
EARLY = re.compile(
    r"\b(intern(?:ship)?|graduate|junior|entry[ -]level|early[ -]career|trainee|apprentice)\b", re.I
)
TECH = re.compile(
    r"\b(software|engineer(?:ing)?|developer|backend|frontend|full[ -]?stack|sde|data|machine learning|ai|ml|devops|cloud|security|qa|qae|quality assurance|technical|it)\b",
    re.I,
)
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|director|manager|lead)\b", re.I)


def early_career(job):
    return bool(
        EARLY.search(job.title)
        and (
            TECH.search(job.title)
            or set(classify(job.title)) & {"design", "ux_research", "design_engineering"}
        )
        and not SENIOR.search(job.title)
    )


def enrich_location(job):
    """Use explicit country/city evidence only; remote alone never establishes India eligibility."""
    if job.country != "Unknown":
        return job
    location = " / ".join(job.locations)
    country = None
    if re.search(
        r"\b(india|bengaluru|bangalore|hyderabad|pune|mumbai|chennai|ahmedabad|gurugram|gurgaon|noida|new delhi)\b",
        location,
        re.I,
    ):
        country = "India"
    elif re.search(r"\b(united states|usa|san jose|san francisco|new york)\b", location, re.I):
        country = "United States"
    if not country:
        return job
    return job.model_copy(
        update={
            "country": country,
            "provenance": {
                **job.provenance,
                "country": {"method": "location_rule", "source_text": location, "confirmed": False},
            },
        }
    )
