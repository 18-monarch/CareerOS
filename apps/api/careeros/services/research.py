"""Bounded web discovery. Search snippets are leads, never eligibility evidence."""

import hashlib
import re
from urllib.parse import urlsplit

import httpx
from careeros.config import get_settings
from careeros.db import utcnow
from careeros.models import Job, Occurrence, ResearchLead, Source
from careeros.schemas import safe_url
from careeros.services.categories import CATEGORIES, classify
from careeros.services.discovery_catalog import early_career, enrich_location
from careeros.services.repository import normalized_url, profile_data, upsert_job
from careeros.services.sources import ADAPTERS, fetch_json
from sqlalchemy import select

QUERY_TERMS = {
    "software": "(software OR SDE)",
    "backend": "backend software",
    "frontend": "frontend developer",
    "fullstack": "full stack developer",
    "data": "machine learning data science",
    "cloud": "cloud devops platform",
    "security": "cybersecurity security",
    "qa": "QA test automation",
    "design": '("product design" OR "UX design" OR "UI design")',
    "ux_research": '"UX research"',
    "design_engineering": '"design engineer" UI',
}


def queries_for(profile):
    prefs = profile["preferences"]
    places = (prefs.get("countries") or ["India"])[:10]
    categories = prefs.get("career_categories") or ["software", "design"]
    return [
        {"category": c, "query": f"{QUERY_TERMS[c]} internship {place} careers apply"}
        for place in places
        for c in categories
        if c in QUERY_TERMS
    ]


async def web_search(query):
    settings = get_settings()
    if not settings.brave_search_api_key:
        raise ValueError("Configure BRAVE_SEARCH_API_KEY to enable broad web search")
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={
                "q": query,
                "count": 10,
                "search_lang": "en",
                "freshness": "pm",
                "text_decorations": "false",
            },
            headers={
                "X-Subscription-Token": settings.brave_search_api_key,
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return response.json().get("web", {}).get("results", [])


def ats_reference(url):
    """Only known ATS hosts and exact public posting routes can trigger network calls."""
    safe_url(url)
    u = urlsplit(url)
    if u.scheme != "https" or u.port not in (None, 443):
        return None
    parts = u.path.strip("/").split("/")
    if not parts or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", parts[0]):
        return None
    if (
        u.hostname in ("job-boards.greenhouse.io", "boards.greenhouse.io")
        and len(parts) == 3
        and parts[1] == "jobs"
        and parts[2].isdigit()
    ):
        return "greenhouse", parts[0], parts[2]
    if (
        u.hostname == "jobs.lever.co"
        and len(parts) in (2, 3)
        and re.fullmatch(r"[a-fA-F0-9-]{36}", parts[1])
        and (len(parts) == 2 or parts[2] == "apply")
    ):
        return "lever", parts[0], parts[1]
    if (
        u.hostname == "jobs.ashbyhq.com"
        and len(parts) in (2, 3)
        and re.fullmatch(r"[a-fA-F0-9-]{36}", parts[1])
        and (len(parts) == 2 or parts[2] == "application")
    ):
        return "ashby", parts[0], parts[1]
    return None


async def verify_posting(url):
    ref = ats_reference(url)
    if not ref:
        return (
            None,
            None,
            "REVIEW_REQUIRED",
            "Open the original employer page to verify this lead. Automatic verification supports Greenhouse, Lever and Ashby posting URLs.",
        )
    kind, board, external = ref
    config = {"board": board, "country": "Unknown"}
    adapter = ADAPTERS[kind](config)
    try:
        if kind == "greenhouse":
            raw = await fetch_json(
                f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{external}"
            )
        elif kind == "lever":
            raw = await fetch_json(f"https://api.lever.co/v0/postings/{board}/{external}")
        else:
            records = await adapter.fetch_jobs()
            raw = next((r for r in records if str(r.get("id")) == external), None)
            if raw is None:
                return (
                    None,
                    None,
                    "UNAVAILABLE",
                    "Posting is absent from the current public employer feed.",
                )
        job = enrich_location(adapter.normalize_job(raw))
        if not early_career(job):
            return (
                None,
                None,
                "OUTSIDE_FOCUS",
                "This posting is outside the supported early-career software/design title categories.",
            )
        return (
            job,
            raw,
            "VERIFIED_LISTING",
            "Posting found in the employer's live public feed. Graduation eligibility and availability still need checking.",
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (404, 410):
            return (
                None,
                None,
                "UNAVAILABLE",
                "The public posting endpoint reports this role unavailable.",
            )
        return (
            None,
            None,
            "CHECK_FAILED",
            f"Public feed returned HTTP {exc.response.status_code}; no eligibility or closure conclusion made.",
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return (
            None,
            None,
            "CHECK_FAILED",
            "Could not verify this posting. No eligibility or closure conclusion made.",
        )


def record_lead(db, user_id, url, **data):
    url = normalized_url(safe_url(url))
    if not url or urlsplit(url).scheme != "https":
        raise ValueError("A public HTTPS posting URL is required")
    key = hashlib.sha256(url.encode()).hexdigest()
    lead = db.scalar(
        select(ResearchLead).where(ResearchLead.user_id == user_id, ResearchLead.url_key == key)
    )
    if not lead:
        lead = ResearchLead(user_id=user_id, url=url, url_key=key, data={})
        db.add(lead)
    lead.data = {**lead.data, **data, "last_discovered_at": utcnow().isoformat()}
    db.commit()
    return lead


async def verify_lead(db, lead):
    from careeros.services.locking import job_lock

    if lead.status == "DISMISSED":
        return lead
    job, raw, status, note = await verify_posting(lead.url)
    meta = {**lead.data, "checked_at": utcnow().isoformat(), "verification_note": note}
    if job:
        kind, board, _ = ats_reference(lead.url)
        with job_lock(db.bind, f"ingest-user:{lead.user_id}") as acquired:
            if not acquired:
                lead.status = "CHECK_FAILED"
                lead.data = {
                    **meta,
                    "verification_note": "Another import is running; retry verification shortly.",
                }
                db.commit()
                return lead
            source = db.scalar(
                select(Source)
                .where(Source.user_id == lead.user_id, Source.kind == kind)
                .filter(Source.name == f"Research: {board}")
                .limit(1)
            )
            if not source:
                source = Source(
                    user_id=lead.user_id,
                    kind=kind,
                    name=f"Research: {board}",
                    enabled=False,
                    config={"board": board, "country": "Unknown", "discovery_managed": True},
                )
                db.add(source)
                db.flush()
            saved, created = upsert_job(db, lead.user_id, job, source, raw)
            saved.data = {
                **saved.data,
                "listing_verification": {
                    "method": "public_ats",
                    "checked_at": meta["checked_at"],
                    "url": lead.url,
                },
                "company_name_note": "Employer board identifier; confirm employer name on the original posting.",
            }
            meta.update(
                {
                    "job_id": saved.id,
                    "added": created,
                    "title": saved.title,
                    "categories": classify(saved.title),
                }
            )
    if status == "UNAVAILABLE" and meta.get("job_id"):
        saved = db.get(Job, meta["job_id"])
        if saved and saved.user_id == lead.user_id:
            for occurrence in db.scalars(select(Occurrence).where(Occurrence.job_id == saved.id)):
                source = db.get(Source, occurrence.source_id)
                if source.name.startswith("Research:"):
                    occurrence.is_active = False
            db.flush()
            active = db.scalar(
                select(Occurrence.id)
                .where(Occurrence.job_id == saved.id, Occurrence.is_active.is_(True))
                .limit(1)
            )
            if not active:
                saved.is_active = False
                saved.data = {**saved.data, "source_closed": True}
    lead.data, lead.status = meta, status
    db.commit()
    return lead


async def run_research(db, user, offset=0):
    settings = get_settings()
    if not settings.brave_search_api_key:
        return {"status": "NOT_CONFIGURED", "leads": 0, "verified": 0, "queries": 0, "errors": 0}
    plan = queries_for(profile_data(db, user))
    if not plan:
        return {"status": "NO_CATEGORIES", "leads": 0, "verified": 0, "queries": 0, "errors": 0}
    offset = offset % len(plan)
    queries = (plan[offset:] + plan[:offset])[: settings.research_query_limit]
    result = {
        "status": "COMPLETE",
        "leads": 0,
        "verified": 0,
        "queries": 0,
        "errors": 0,
        "next_query_offset": (offset + len(queries)) % len(plan),
    }
    seen = set()
    for index, query in enumerate(queries):
        if index:
            import asyncio

            await asyncio.sleep(1.05)
        try:
            records = await web_search(query["query"])
            result["queries"] += 1
            for record in records:
                url = record.get("url", "")
                if url in seen or len(seen) >= settings.research_result_limit:
                    continue
                try:
                    lead = record_lead(
                        db,
                        user.id,
                        url,
                        title=str(record.get("title", ""))[:300],
                        snippet=str(record.get("description", ""))[:1800],
                        query=query["query"],
                        categories=[query["category"]],
                    )
                except ValueError:
                    continue
                seen.add(url)
                result["leads"] += 1
                await verify_lead(db, lead)
                result["verified"] += int(lead.status == "VERIFIED_LISTING")
                result["errors"] += int(lead.status == "CHECK_FAILED")
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            result["errors"] += 1
    if result["errors"]:
        result["status"] = "PARTIAL" if result["queries"] else "FAILED"
    return result


def research_brief(db, user):
    from careeros.services.repository import candidate_context, ranked_jobs

    profile, skills, projects, prefs = candidate_context(db, user)
    groups = {key: {"id": key, "label": label, "items": []} for key, label in CATEGORIES.items()}
    for job in ranked_jobs(db, user):
        if job["is_demo"] or not job["is_active"]:
            continue
        m = job["match"]
        if m["eligibility"]["state"] in ("CLOSED", "NOT_ELIGIBLE"):
            continue
        evidence = [
            p["name"]
            for p in projects
            if set(p.get("verified_skills", [])) & set(m["strong_matches"])
        ]
        verified = job.get("listing_verification")
        why = (
            ("Matching skills: " + ", ".join(m["strong_matches"][:6]))
            if m["strong_matches"]
            else "Add your skill evidence to assess fit; a category match alone does not establish readiness."
        )
        next_step = "Check the original eligibility and your availability before applying."
        if m["classification"] == "APPLY_NOW":
            next_step = "Review the original posting, then prepare an application."
        elif m["missing_required"]:
            next_step += " Prepare: " + ", ".join(m["missing_required"][:3]) + "."
        item = {
            "id": job["id"],
            "company": job["company_name"],
            "title": job["title"],
            "country": job["country"],
            "locations": job["locations"],
            "score": m["score"],
            "eligibility": m["eligibility"],
            "classification": m["classification"],
            "why": why,
            "projects": evidence,
            "next_step": next_step,
            "application_url": job["application_url"],
            "deadline": job["application_deadline"],
            "first_discovered": job["created_at"],
            "posted_at": job["posted_at"],
            "last_checked": (verified or {}).get("checked_at") or job["last_seen_at"],
            "categories": job["categories"],
        }
        for cat in job["categories"]:
            groups[cat]["items"].append(item)
    return list(groups.values())


async def recheck_leads(db, user):
    # Imported research postings are refreshed even if the search key is later removed.
    leads = list(
        db.scalars(
            select(ResearchLead)
            .where(
                ResearchLead.user_id == user.id,
                ResearchLead.status != "DISMISSED",
                ResearchLead.data["job_id"].as_string().is_not(None),
            )
            .order_by(ResearchLead.updated_at)
            .limit(get_settings().research_result_limit)
        )
    )
    checked, errors = 0, 0
    for lead in leads:
        if not lead.data.get("job_id"):
            continue
        await verify_lead(db, lead)
        checked += 1
        errors += int(lead.status == "CHECK_FAILED")
    return {"checked": checked, "errors": errors}
