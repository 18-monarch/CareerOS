# API reference

Interactive documentation: `http://localhost:8000/docs`. The complete machine-readable schema is `packages/shared/openapi.json`, regenerated using `.venv/bin/python scripts/export-openapi.py`.

All endpoints below except health and initial authentication require the access cookie. Mutations also require `X-CSRF-Token` matching the CSRF cookie/session. Browser requests use the Next.js `/api` gateway; scripts can call FastAPI directly using a cookie jar and the returned CSRF token.

| Resource | Operations |
|---|---|
| `/health`, `/ready` | Liveness / migrated-database readiness |
| `/auth/register`, `/auth/login` | POST credentials; returns user summary and CSRF token, sets cookies |
| `/auth/me`, `/auth/refresh`, `/auth/logout` | GET identity, POST rotation, POST revocation |
| `/auth/password` | POST current/new password; revokes all sessions and issues a new current session |
| `/profile` | GET / PUT education, preferences and profile links |
| `/skills`, `/skills/{id}` | GET / POST upsert self-assessment / DELETE |
| `/projects`, `/projects/{id}` | GET / POST / PUT / DELETE |
| `/projects/{id}/mastery` | PUT a topic assessment |
| `/resumes`, `/resumes/{id}` | GET / POST / PUT metadata / DELETE |
| `/jobs` | GET search/filter/page / POST manual opportunity |
| `/jobs/{id}` | GET full evidence and explanations / PUT reviewed corrections |
| `/jobs/{id}/eligibility`, `/jobs/{id}/match` | GET deterministic result |
| `/jobs/{id}/archive`, `/jobs/{id}/restore` | PATCH persistent manual archive / explicit restore |
| `/campus/parse`, `/campus/jobs` | POST parse proposal / POST reviewed notice / GET campus roles |
| `/applications`, `/applications/{id}` | GET / POST create / PATCH stage and details |
| `/applications/{id}/events`, `/applications/metrics` | GET immutable history / funnel metrics |
| `/dashboard` | GET action-oriented aggregate |
| `/learning/recommendations`, `/learning/progress` | GET skill gaps / GET and PUT personal progress |
| `/dsa`, `/dsa/{id}` | GET topic totals + logs / POST log / DELETE log |
| `/sources`, `/sources/health` | GET private source health / POST source |
| `/sources/{id}` | PUT configuration; imported source identity cannot be changed |
| `/sources/{id}/toggle`, `/sources/{id}/ingest` | PATCH enabled flag / POST bounded ingestion |
| `/notifications`, `/notifications/{id}/read` | GET records / PATCH read |
| `/notifications/generate` | POST idempotent high-match/deadline/daily checks; no direct email send |
| `/market-reports`, `/market-reports/{id}` | GET / POST sourced report / DELETE |
| `/visa-rules`, `/visa-rules/{id}` | GET with stale flag / POST sourced rule note / DELETE |

## Search

`GET /jobs?q=backend&country=India&eligibility=ELIGIBLE&min_score=60&page=1&page_size=20&sort=match`

Also supports `role`, `company`, `city`, `remote`, `employment_type`, `source`, `skill`, `state`, `graduation_year`, `max_cgpa`, `deadline_before`. Sort is match (default), deadline or newest. Response: `{items,total,page,page_size}`. Page size is limited to 100.

## Example manual posting

```json
{
  "company_name": "Your verified company",
  "title": "Software Engineer Intern",
  "normalized_role": "Software Engineer",
  "country": "India",
  "source": "manual",
  "description": "Paste the actual role description here.",
  "requirements": {"minimum_cgpa": 7.0, "allowed_graduation_years": [2028]},
  "required_skills": ["Python", "SQL"],
  "preferred_skills": ["Docker"],
  "provenance": {"minimum_cgpa": {"method": "manual", "confirmed": true}}
}
```

Use actual application URLs and deadline timestamps from the source; leave unknowns null. Never enter a sample as if it were a real posting. The job schema has an `is_demo` field for explicit synthetic entries.

## Errors

```json
{"error":{"message":"Validation failed","fields":[{"field":"body.cgpa","message":"..."}],"request_id":"..."}}
```

Error responses never echo submitted passwords or tokens. Use the request ID to correlate safe logs. Invalid credentials → 401; missing/invalid CSRF or wrong Origin → 403; record not owned/found → 404; uniqueness/busy-writer/source-identity conflict or deleting a resume used by an application → 409; invalid schema → 422; throttle → 429; backend unavailable at gateway → 502.
