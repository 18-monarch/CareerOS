# CareerOS V1 engineering handoff

## What was built

A functional personal career workspace: editable candidate profile; Greenhouse, Lever, Ashby and approved JSON-feed ingestion; manual/campus jobs; canonical deduplication; deterministic eligibility and matching; application tracking with immutable history; learning priorities; DSA/project mastery; notifications; source health; sourced market and international-rule notes. Includes responsive dark/light frontend, REST backend, workers, migrations, explicit demo seed, tests, CI, deployment configuration and study documentation.

## Architecture

Next.js presents the workspace and proxies same-origin requests to FastAPI. SQLAlchemy persists data in PostgreSQL. Python cron commands reuse backend domain services. Public-feed adapters normalize external data before deduplication, eligibility and scoring. Optional Resend/AI providers have useful no-key paths. See ARCHITECTURE.md for the Mermaid diagram and boundaries.

## How to run locally

Use Python 3.12+, Node 24 and PostgreSQL through Docker, or the documented SQLite development fallback. From the repository root:

```bash
cp .env.example .env
cp apps/web/.env.example apps/web/.env.local
docker compose up -d db
make install
make migrate
export DEMO_PASSWORD='choose-your-own-long-password'
make seed
make api
```

In another terminal run `make web`, then open http://localhost:3000. The seed email is `mohit@example.com`; the password is the value you supplied. Alternatively register an empty account. README.md contains the exact non-Make commands, Windows notes and worker commands. API documentation runs at http://localhost:8000/docs.

## Environment variables required

Backend: DATABASE_URL, FRONTEND_ORIGIN, ENVIRONMENT and COOKIE_SECURE. Frontend server: API_BASE_URL and FRONTEND_ORIGIN. The checked-in examples use local development values. Production requires PostgreSQL, HTTPS and secure cookies. Resend credentials and AI key/model are optional. Official custom feeds require an operator-maintained ALLOWED_FEED_HOSTS allowlist. Set REGISTRATION_ENABLED=false after personal onboarding. Keep all actual secrets outside Git.

## How to deploy

Create Neon PostgreSQL and use its direct connection endpoint. Apply the Render Blueprint for API and cron services; set its environment group and run Alembic migrations. Deploy apps/web to Vercel and configure the backend URL and matching public frontend origin on both services. Run the documented smoke checks. DEPLOYMENT.md covers order, schedules and rollback considerations. No cloud resource has been provisioned and no GitHub remote has been pushed by this delivery.

## Test results

36 backend tests, 5 frontend component tests and 2 Chromium E2E tests passed. Lint, formatting, TypeScript and production build passed. Migrations, all seven worker commands, navigation and mobile layout were exercised. Live Greenhouse ingestion and Ashby normalization were verified. PostgreSQL SQL/type checks passed 28 tests using embedded PostgreSQL; native multi-session PostgreSQL concurrency remains a deployment/CI gate. Read VERIFICATION.md for evidence and precise exclusions.

## Known limitations

This is intended for personal/private use. Account verification, self-service password recovery and MFA are not implemented. Resume support is metadata only. Market and visa notes require sourced manual review. Ranking loads a user's jobs into memory. Missing source postings are not automatically closed. Heuristic scores are not hiring probabilities. Docker images, cloud deployment, real email and credentialed AI calls were not executed here. Full native PostgreSQL CI is provided but has not run remotely.

## Next best improvements

1. Run native PostgreSQL CI and hosted smoke checks with actual deployment credentials.
2. Add verified account recovery before allowing public registration.
3. Add source configuration editing, source-specific closure reconciliation and richer job revision history.
4. Generate frontend types from OpenAPI; move candidate filtering into SQL only when volume warrants it.

## Most important files to study

- apps/api/careeros/main.py, schemas.py and routers/: API boundaries and validation.
- apps/api/careeros/models.py and apps/api/alembic/versions/: relational design and schema evolution.
- apps/api/careeros/security.py and routers/auth.py: cookies, CSRF, password hashing and ownership.
- apps/api/careeros/services/eligibility.py and matching.py: deterministic rules and explainable weighted scores.
- apps/api/careeros/services/sources.py, repository.py and ingestion.py: adapter contracts, deduplication and fault isolation.
- apps/worker/worker/__main__.py and services/locking.py: scheduled processing and locks.
- apps/web/components/ and app/api/[...path]/route.ts: UI state and same-origin integration.
- apps/api/tests/, apps/web/tests/ and .github/workflows/ci.yml: verification and delivery gates.

## How this project teaches me software engineering

Start with LEARNING_GUIDE.md. Trace one opportunity from ingestion to dashboard before reading every file. Then change one eligibility rule and its test; follow an API request through Pydantic, authorization, SQLAlchemy and the response; inspect a migration and immutable event history; trace a source retry and deduplication decision; run a worker twice and observe idempotency; finally read the CI and deployment configurations. The guide covers REST APIs, PostgreSQL, authentication, database design, ingestion, algorithms, background processing, testing, CI/CD, deployment and system design through concrete files, trade-offs and interview questions.
