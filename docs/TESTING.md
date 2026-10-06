# Testing and verification

Tests assert domain behavior and cross-layer workflows, not only implementation details.

## Backend

`pytest -q` uses temporary SQLite databases by default. `TEST_DATABASE_URL` switches fixtures to a disposable PostgreSQL database; tests create/drop tables, so **never point it at production**.

- `test_domain.py`: CGPA/graduation/degree/experience/authorization boundaries, closure at exact deadline, unknown facts, unconfirmed extraction, preferred skills, ranking suppression, evidence honesty, learning demand, parser provenance, URL validation.
- `test_api.py`: registration/login, CSRF, origin rejection, refresh rotation, logout, rate limits, cross-tenant isolation, profile edit, all application milestones, funnel metrics, persistent records, duplicate notifications, manual/campus entries, job correction and supporting modules.
- `test_sources.py`: vendor normalization fixtures, transient HTTP retry behavior, ingestion savepoints, source failure isolation, repeat upserts, cross-source deduplication, distinct requisitions, SSRF allowlist rejection and duplicate process locks.

Run migrations separately: `alembic upgrade head && alembic check`. CI tests on native PostgreSQL 17, then migrates, seeds and executes workers. Migration triggers are installed only by Alembic; unit fixtures use metadata tables. The verification script additionally checks immutability against a migrated database.

## Frontend

`npm run test`: component tests for visible eligibility labels, demo labels, detail/save callbacks, saved-job disabled state and useful error/empty UI.

`npm run lint`, `npm run typecheck`, `npm run build`: syntax, types, framework rules and production compilation.

## Browser end-to-end

Install Chromium once with `npx playwright install chromium`. Start backend and production frontend, seed a demo account, set `DEMO_PASSWORD`, and run `npm run test:e2e` from `apps/web`.

The suite creates an independent test account, edits the profile, adds a role, checks eligibility and explanations, saves it, advances through Applied/OA/Interview, verifies history/dashboard/learning, generates notifications, visits every primary route, checks mobile overflow and records screenshots. A separate test logs into the seed account, inspects demo data and checks light/dark themes.

`scripts/verify-browser.sh` can start both servers and run the suite. It uses `.venv`, expects a migrated/seeded database and an existing frontend build. Optional environment variables: `WEB_PORT`, `API_PORT`, `DEMO_PASSWORD`, `CHROMIUM_EXECUTABLE_PATH` for an already installed portable browser, and `SKIP_AGENT_BROWSER=1` to run Playwright directly.

Browser evidence belongs in `docs/screenshots`; transient traces/reports are ignored. CI uploads failure screenshots/traces as workflow artifacts.

## Network integration checks

Public-source fixture tests are deterministic and run offline. Live checks are separately reported in `VERIFICATION.md`; public boards can change, close or restrict traffic after a passing check. A source returning zero jobs is not proof of a normalization failure. Email/LLM network integration is not considered verified without configured credentials.

## What passing tests do not establish

A production build is not proof of deployment. SQLite is not proof of native PostgreSQL concurrency. Embedded PostgreSQL validates SQL/type behavior but not multi-session advisory locking. A captured desktop screenshot does not prove every mobile dialog fits. No test here predicts hiring outcomes or legal eligibility.
