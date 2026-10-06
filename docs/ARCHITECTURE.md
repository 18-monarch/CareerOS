# Architecture

CareerOS has one domain backend, one browser UI and one CLI worker entry point. API routes own HTTP concerns. Domain services implement business rules. Source adapters isolate vendor differences. SQLAlchemy models and Alembic migrations own persistence.

```mermaid
flowchart TD
  UI["Browser workspace"] --> BFF["Next.js same-origin gateway"]
  BFF --> Routes["FastAPI routes + auth"]
  Routes --> Domain["Pure eligibility and matching"]
  Routes --> Repo["Persistence services"]
  Cron["Worker commands"] --> Ingest["Adapters and normalization"]
  Ingest --> Repo
  Cron --> Domain
  Domain --> Alerts["Priorities and notification records"]
  Repo --> DB["PostgreSQL"]
  Alerts --> DB
```

## Boundaries

- `apps/web/app/api/[...path]/route.ts`: forwards approved path segments and selected headers to one server-configured origin. It is not an open proxy.
- `apps/api/careeros/routers`: authenticated resource boundaries, Pydantic input validation, server-side ownership and consistent HTTP errors.
- `services/eligibility.py`: deterministic five-state hard-rule decisions; no network or LLM.
- `services/matching.py`: weights and set intersections; configurable preferences; pure results.
- `services/repository.py`: user context loading, canonical identity, upsert and serialization.
- `services/sources.py`: shared adapter contract and bounded public HTTP access.
- `services/ingestion.py`: transactions/savepoints, failure isolation and source-run evidence.
- `services/notifications.py`: records first; delivery second; email optional.
- `apps/worker/worker/__main__.py`: schedules call the same services instead of duplicating logic.

## Request example

A job-detail request authenticates a hashed access token, checks `job.user_id`, loads the profile and explicitly recorded skill/project evidence, evaluates hard requirements, computes fit, and returns both explanations and raw fields. TanStack Query caches that response briefly and invalidates relevant data after a mutation. Scores shown after profile updates are recomputed from current data, avoiding stale cache decisions.

## Persistence trade-offs

Identity/ownership/join-heavy relationships are relational. Variable source requirements, extraction evidence, preferences and low-volume notes use validated JSON. Project technologies and verified skills are small JSON lists; they are not globally normalized joins in V1. Eligibility is included in `job_matches.data` rather than duplicated in a separate table. Market and visa records include country names; a separate country catalogue is unnecessary until country metadata becomes a maintained dataset.

Synchronous SQLAlchemy keeps transaction lifetimes explicit and easy to debug. FastAPI sync endpoints run in its threadpool; source network requests are async. Manual ingestion is bounded but can outlast a serverless gateway timeout for unusually large boards. Use the cron worker for large sources. No queue is needed initially; a future queue can call `ingest_source` without changing matching.

## Consistency

A per-user ingest lock protects cross-source deduplication and a unique canonical key guards collisions. Upserts are single-transaction, malformed records roll back to a savepoint, and each source commits its own run. Refresh and status updates use database row locks where supported. Notifications have both unique keys and locking. Application events have append-only database triggers. Tests use disposable databases.

## Scaling boundary

Avoid N+1 reads with joined/select-in relationships; the user-facing search still computes all matches in memory. Complexity is approximately O(J × (S + P)) for J jobs, S candidate/job skill inputs and P project evidence, plus O(J log J) sorting. This is a deliberate personal-scale trade-off. At larger volume, filter coarse SQL candidates first, use persisted versioned match results and cursor pagination. Do not add distributed caches before measuring.
