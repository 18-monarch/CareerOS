"""Browser-test API: only the external HTTP transport uses deterministic fixtures.

Run through verify-browser.sh against its disposable database. This file is not
installed in the production careeros package.
"""

import os
from datetime import timedelta

import httpx

if os.environ.get("CAREEROS_E2E") != "1" or os.environ.get("ENVIRONMENT") != "development":
    raise RuntimeError("The fixture server requires explicit disposable E2E configuration")

from careeros.db import utcnow  # noqa: E402
from careeros.main import app  # noqa: F401, E402
from careeros.services import discovery, sources  # noqa: E402

if os.environ.get("E2E_AUTODISCOVERY") == "true":
    discovery.CATALOG = (
        {
            "kind": "greenhouse",
            "board": "careeros-fixture",
            "company_name": "Fixture Company",
            "url": "https://example.com/fixture-careers",
        },
    )

real_fetch = sources.fetch_json
real_normalize = sources.Greenhouse.normalize_job


def upstream(request):
    if request.url.host == "boards-api.greenhouse.io" and "/careeros-fixture/" in request.url.path:
        job = {
            "id": "fixture-1",
            "requisition_id": "fixture-requisition",
            "title": "Software Engineer Intern",
            "content": "CGPA: 7.0\nBatch: 2028\nRequired: Python\nPreferred: Docker",
            "absolute_url": "https://example.com/fixture-internship",
            "location": {"name": "Ahmedabad"},
            "application_deadline": (utcnow() + timedelta(days=2)).isoformat(),
        }
        records = [job, {**job, "id": "fixture-2"}]
        if os.environ.get("E2E_AUTODISCOVERY") == "true":
            records += [
                {**job, "id": "senior", "title": "Senior Software Engineer"},
                {**job, "id": "hr", "title": "HR Intern"},
            ]
        return httpx.Response(200, json={"jobs": records})
    return httpx.Response(404, json={"error": "No fixture board found"})


async def fixture_fetch(url, client=None):
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as transport:
        return await real_fetch(url, transport)


def demo_normalize(self, raw):
    return real_normalize(self, raw).model_copy(update={"is_demo": True})


sources.fetch_json = fixture_fetch
sources.Greenhouse.normalize_job = demo_normalize
