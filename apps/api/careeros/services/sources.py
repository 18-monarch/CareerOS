"""Public API adapters. No login bypass, arbitrary-page scraping, or application submission."""

import asyncio
import ipaddress
import logging
import socket
from abc import ABC, abstractmethod
from urllib.parse import urlsplit

import httpx
from careeros.config import get_settings
from careeros.schemas import JobIn
from careeros.services.parsing import clean_html, parse_notice

logger = logging.getLogger("careeros.sources")


async def fetch_json(url, client=None):
    async def request(c):
        for attempt in range(3):
            try:
                # No redirects: avoids changing to an unapproved host after validation.
                async with c.stream(
                    "GET",
                    url,
                    timeout=20,
                    follow_redirects=False,
                    headers={
                        "User-Agent": "CareerOS/1.0 public-job-board-client",
                        "Accept": "application/json",
                    },
                ) as response:
                    response.raise_for_status()
                    chunks, total = [], 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > 10 * 1024 * 1024:
                            raise ValueError("Feed exceeds 10 MiB limit")
                        chunks.append(chunk)
                    import json

                    return json.loads(b"".join(chunks))
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                retryable = not isinstance(
                    exc, httpx.HTTPStatusError
                ) or exc.response.status_code in (429, 500, 502, 503, 504)
                logger.warning(
                    "source_request_retry",
                    extra={
                        "host": urlsplit(url).hostname,
                        "attempt": attempt + 1,
                        "error_type": type(exc).__name__,
                    },
                )
                if attempt == 2 or not retryable:
                    raise
                await asyncio.sleep(2**attempt)

    if client:
        return await request(client)
    async with httpx.AsyncClient() as c:
        return await request(c)


class JobSourceAdapter(ABC):
    source_name: str

    def __init__(self, config):
        self.config = config

    @abstractmethod
    async def fetch_jobs(self): ...

    @abstractmethod
    def normalize_job(self, raw) -> JobIn: ...

    async def health_check(self):
        records = await self.fetch_jobs()
        return {"ok": True, "count": len(records)}

    def common(self, title, description):
        parsed = parse_notice(description)["job"]
        role = (
            "Backend Engineer"
            if "backend" in title.lower()
            else "Full-Stack Engineer"
            if any(x in title.lower() for x in ("full stack", "full-stack"))
            else "Software Engineer"
            if any(x in title.lower() for x in ("software", "engineer", "developer"))
            else title
        )
        return {
            "company_name": self.config.get("company_name") or self.config.get("board", "Unknown"),
            "title": title,
            "description": clean_html(description),
            "source": self.source_name,
            "country": self.config.get("country", "Unknown"),
            "normalized_role": role,
            "employment_type": "internship" if "intern" in title.lower() else "full-time",
            "requirements": parsed["requirements"],
            "required_skills": parsed["required_skills"],
            "preferred_skills": parsed["preferred_skills"],
            "provenance": parsed["provenance"],
        }


class Greenhouse(JobSourceAdapter):
    source_name = "greenhouse"

    async def fetch_jobs(self):
        payload = await fetch_json(
            f"https://boards-api.greenhouse.io/v1/boards/{self.config['board']}/jobs?content=true"
        )
        return payload["jobs"]

    def normalize_job(self, raw):
        return JobIn(
            **self.common(raw["title"], raw.get("content", "")),
            external_id=str(raw["id"]),
            requisition_id=raw.get("requisition_id"),
            locations=[raw.get("location", {}).get("name", "Unknown")],
            application_url=raw["absolute_url"],
            source_url=raw["absolute_url"],
            posted_at=raw.get("first_published"),
            application_deadline=raw.get("application_deadline"),
        )


class Lever(JobSourceAdapter):
    source_name = "lever"

    async def fetch_jobs(self):
        records = []
        for skip in range(0, 10000, 100):
            batch = await fetch_json(
                f"https://api.lever.co/v0/postings/{self.config['board']}?mode=json&limit=100&skip={skip}"
            )
            records.extend(batch)
            if len(batch) < 100:
                return records
        raise ValueError("Lever board exceeds safe pagination limit")

    def normalize_job(self, raw):
        description = (
            raw.get("descriptionPlain", "")
            + "\n"
            + "\n".join(clean_html(x.get("content", "")) for x in raw.get("lists", []))
        )
        salary = raw.get("salaryRange") or {}
        return JobIn(
            **self.common(raw["text"], description),
            external_id=str(raw["id"]),
            locations=[raw.get("categories", {}).get("location", "Unknown")],
            application_url=raw.get("applyUrl"),
            source_url=raw.get("hostedUrl"),
            remote_status=raw.get("workplaceType")
            if raw.get("workplaceType") in ("remote", "onsite", "hybrid")
            else "unknown",
            salary_min=salary.get("min"),
            salary_max=salary.get("max"),
            salary_currency=salary.get("currency"),
            salary_period=salary.get("interval"),
        )


class Ashby(JobSourceAdapter):
    source_name = "ashby"

    async def fetch_jobs(self):
        payload = await fetch_json(
            f"https://api.ashbyhq.com/posting-api/job-board/{self.config['board']}?includeCompensation=true"
        )
        return payload["jobs"]

    def normalize_job(self, raw):
        return JobIn(
            **self.common(
                raw["title"], raw.get("descriptionPlain", raw.get("descriptionHtml", ""))
            ),
            external_id=str(raw["id"]),
            locations=[raw.get("location", "Unknown")],
            remote_status="remote" if raw.get("isRemote") else "unknown",
            application_url=raw.get("applyUrl"),
            source_url=raw.get("jobUrl"),
            posted_at=raw.get("publishedAt"),
        )


class OfficialFeed(JobSourceAdapter):
    """Explicitly operator-approved JSON feed in CareerOS normalized format."""

    source_name = "official"

    async def fetch_jobs(self):
        url = self.config["feed_url"]
        parsed = urlsplit(url)
        hosts = [
            h.strip().lower() for h in get_settings().allowed_feed_hosts.split(",") if h.strip()
        ]
        if (
            parsed.scheme != "https"
            or parsed.hostname not in hosts
            or parsed.port not in (None, 443)
        ):
            raise ValueError("Official feed host must be explicitly approved by the operator")
        addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, 443)
        if any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Private addresses are not allowed")
        result = await fetch_json(url)
        return result["jobs"] if isinstance(result, dict) else result

    def normalize_job(self, raw):
        return JobIn(**{**raw, "source": "official"})


class Manual(JobSourceAdapter):
    source_name = "manual"

    async def fetch_jobs(self):
        return []

    def normalize_job(self, raw):
        return JobIn(**{**raw, "source": self.source_name})


class Campus(Manual):
    source_name = "campus"


ADAPTERS = {
    "greenhouse": Greenhouse,
    "lever": Lever,
    "ashby": Ashby,
    "official": OfficialFeed,
    "manual": Manual,
    "campus": Campus,
}
