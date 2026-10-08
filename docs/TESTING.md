# Testing and verification

Tests assert domain behavior and cross-layer workflows, not only implementation details.

## Backend

`pytest -q` uses temporary SQLite databases by default. `TEST_DATABASE_URL` switches fixtures to disposable PostgreSQL. Tests create/drop all application tables: **never point it at production**.

- `test_domain.py`: graduation/CGPA/degree/experience/authorization boundaries, exact deadlines, unknown facts, extraction uncertainty, preferred skills, ranking suppression, evidence honesty, learning demand, parsing and URL validation.
- `test_api.py`: registration/login, CSRF/origin/rotation/logout/rate limits, tenant isolation, profile editing, milestones/history/funnel, notifications, manual/campus jobs and supporting modules.
- `test_sources.py`: vendor fixtures, HTTP retries, savepoints, source failure isolation, repeat upserts, deduplication/requisitions, SSRF restrictions and duplicate locks.
- `test_reliability.py`: conservative occurrence closure/reappearance, archive persistence, source edits/identity guards, shared writes, password whitespace/change/recovery, resume integrity, chunked body limits, seven-day summaries, uncertain dates, readiness revision, provider retries and continuation after worker failure.
- `test_migrations.py`: actual Alembic upgrade, seed, immutable UPDATE/DELETE rejection, latest downgrade/upgrade with data retention, and schema drift. Runs on the configured disposable SQLite or PostgreSQL database.

Most fixtures use metadata tables; the migration test deliberately installs actual triggers and restores the isolated database afterward. Run release migrations independently with `alembic upgrade head && alembic check` as well. CI runs the suite, migrations, seed and workers on native PostgreSQL 17.

## Frontend

From `apps/web`, run `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run build`. Component tests cover visible decisions/demo labels, detail/save callbacks, saved state, useful errors/empty UI and accessible labels.

## Complete browser verification

After installing backend dependencies and from the repository root:

```bash
cd apps/web
npm ci
npx playwright install chromium
npm run build
cd ../..
scripts/verify-browser.sh
```

The script creates a fresh temporary SQLite database, migrates and seeds it, starts the real API plus production frontend, runs all three Playwright journeys and shuts down its servers. It never reuses the developer's root `.env` database. A test-only server entry point replaces the external Greenhouse transport with deterministic source fixtures; it refuses to run without explicit development/test settings. Application logic remains real.

Optional variables: `PYTHON_BIN` (defaults to `.venv/bin/python`), `WEB_PORT`, `API_PORT`, `DEMO_PASSWORD`, `CHROMIUM_EXECUTABLE_PATH` (portable browser), and `E2E_DATABASE_URL` for a **disposable** PostgreSQL database. If the frontend build used `NEXT_DIST_DIR`, pass the same value to this script. Native PostgreSQL browser verification is configured in CI.

Journeys cover manual job → eligibility → save → application stages/history → alerts/dashboard/learning; seeded login/themes/responsive navigation; and source failure → edit → retry → deduplication → human confirmation → archive/refresh/restore → resume/password edit → new-password login. Screenshots and traces are recorded in ignored test output; CI uploads them on failures.

For debugging against already running servers, `npm run test:e2e` is also available, but the fixture-feed journey is skipped unless `E2E_FIXTURE_FEED=1` and the fixture server are configured. Use the provided harness for complete verification.

## Containers and external integrations

The CI `containers` job builds Compose images, starts PostgreSQL/API/frontend, checks readiness through the frontend gateway, seeds and executes `run-cycle`. It is a configured gate until that workflow actually runs.

Source fixtures are deterministic and offline. Live checks are reported separately in `VERIFICATION.md`; boards can change after a passing check. A zero-record feed is not proof of normalization failure. Provider tests use mocked transports; real email/AI integration requires configured credentials and separate smoke checks.

## What passing tests do not establish

A production build is not proof of deployment. SQLite is not proof of native PostgreSQL concurrency. Embedded PostgreSQL validates SQL/type behavior but not multi-session advisory locking. Screenshots do not prove every possible mobile dialog fits. No test predicts hiring outcomes or legal eligibility.

## Windows installation regression

The requirements files are generated with `uv pip compile --universal`; retain platform markers when regenerating them. Windows must skip `uvloop` and include `tzdata` (plus `colorama` for development). `test_portability.py` checks both dependency sets and exercises lock contention in a separate Python process, including release after an exception. Local SQLite locks use `msvcrt` on Windows and `fcntl` on Unix.

The `windows-local` CI job installs the actual requirements on Windows, checks dependencies, runs the backend suite, migrates/seeds SQLite, runs the worker, and builds/tests the frontend. This job requires a pushed GitHub repository before it can execute. Local Linux results do not establish native Windows runtime correctness.
