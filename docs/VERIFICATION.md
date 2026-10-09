# Verification

## October 9 — Netlify/Render deployment preparation

87 backend tests and 8 frontend tests passed, including locked startup migration, external-worker queue status, preview isolation, origin protection and separate cookie forwarding. Lint/type checks, production build and an offline Netlify CLI build using the actual `netlify.toml` passed. The Blueprint validates against Render's current official JSON schema. Offline Netlify build does not prove deployed adapter behavior.

The latest `e91a05` migration, downgrade/upgrade, seed, schema drift, JSON research query and immutable-history triggers passed on PostgreSQL 18.3 via PGlite. Native PostgreSQL installation was blocked by this environment's process permissions, so multi-session validation remains the configured GitHub CI gate. No Neon project or Render/Netlify deployment has been created. The local Git repository has no remote and no accessible CareerOS repository was found in the connected GitHub installation.

The new browser journey checks that an external-worker installation allows queueing, preserves pause after reload and never claims that its API background thread is running. Production URL login, cron execution and actual email delivery remain post-deployment checks.

## October 9, 2026 — research and application release

Executed: **85 backend tests**, **5 frontend component tests**, lint/format/type checks, production build and **7 Chromium scenarios** (six standard scenarios plus the separately enabled background discovery journey). Application adapter checks use controlled browser fixtures; no real employer application was sent.

A live public-feed run fetched **226 postings from ten boards**, filtered 219 and imported **7 internships**, including a Product Design Intern role in India, with zero source errors. Five imported roles were located in India and two in the US. Counts are a point-in-time integration check; eligibility is not inferred from role presence.

SQLite migration head `e91a05`, downgrade/upgrade, schema drift, backup and data retention checks passed. The current release has not been run on native Windows or native PostgreSQL. Brave HTTP contracts, search failure handling and query rotation were tested with fixtures; credentialed live Brave search, live email, cloud deployment and real employer submissions were not performed. UI screenshots use deterministic fixtures.

See [START-HERE.md](../START-HERE.md) for supported behavior and setup. The following sections record earlier release evidence and do not establish current native-platform execution.

# Engineering verification report

Last updated: 8 October 2026. This report distinguishes executed checks from supplied configuration. No cloud deployment is claimed.

## Automatic discovery — 8 October 2026

Implemented API-started background checks, persisted per-user schedule/pause state, starter-source bootstrap, technical early-career filtering, visible controls/status and richer opportunity digests. Migration head is now `d82f04`; all four migrations and schema drift checks passed on SQLite. The new migration has not yet been executed on native PostgreSQL.

Executed for this update: **68 backend tests**, **5 component tests**, lint/type checks, a fresh production build and **4 Chromium browser workflows** passed. The added journey registers an empty account, receives imported jobs without configuring a source or triggering a scan, pauses/reloads/resumes, and confirms repeat import creates no duplicates. It uses the actual background thread/API/database/frontend with only the external feed transport mocked. Mobile screenshots use reduced motion to avoid capturing the responsive sidebar mid-transition.

A separate real internet run checked all six catalog feeds: **103 postings fetched, 96 filtered out, 7 technical internships imported, zero errors**. Five imported roles were located in India, two in the US; a repeat scan added zero. No promise of 2028 eligibility is inferred from these counts. Current native Windows/PostgreSQL execution and remote CI remain unverified.

## Windows installation fix — 8 October 2026

The user's Windows log exposed unconditional `uvloop` installation plus download timeout/reset errors. The dependency locks were regenerated with `--universal`, preserving existing versions while adding platform markers and Windows-only dependencies. SQLite job locks now use Windows `msvcrt` or Unix `fcntl` as appropriate. Frontend metadata and setup docs now specify Node 24.15+; the reported Node 24.8 did not satisfy some installed packages.

Executed for this fix: clean Python dependency installation/check, **61 backend tests passed**, **5 frontend component tests passed**, lint/type checks and a fresh production build. New regression coverage checks Windows dependency selection and actual inter-process lock contention/release. Native Windows execution is **not claimed**: the new `windows-local` CI job is configured but has not run remotely. Earlier browser and PostgreSQL evidence below is from October 6, not a Windows test.

## October 6 baseline: executed and passed

| Check | Result / evidence |
|---|---|
| Backend unit/integration suite | **58 tests passed** on SQLite, covering rules, ranking, parsing, deduplication, auth/CSRF/rotation, ownership, account recovery, persistence, job/source/resume edits, closure reconciliation, notifications, retries and body limits |
| Real migrations | All three migrations applied on SQLite and embedded PostgreSQL; head **`c61f03`** |
| Migration integrity | Seeded data retained across latest downgrade/upgrade; UPDATE and DELETE against application events rejected; original event retained |
| Schema drift | `alembic check`: no new upgrade operations detected on SQLite and embedded PostgreSQL |
| Worker CLI | **All eight commands** executed against a fresh migrated/seeded SQLite database without errors; repeated daily, deadline and weekly runs each created zero duplicate notifications |
| Frontend lint and TypeScript | Passed on authored source; canonical generated-type configuration restored after QA builds |
| Frontend unit tests | **5 component tests passed**: decision/demo labels, functional actions, disabled saved state, empty/error UI and accessible labels |
| Production build | Next.js 16.3.8 production build succeeded, including the App Router and same-origin gateway |
| Browser workflows | **3 Playwright/Chromium tests passed**, with real production frontend, FastAPI, migrated SQLite and an isolated fixture feed |
| Navigation and responsive views | All primary workspace routes visited; no uncaught page errors in the journeys; 1280px desktop and 390px mobile screenshots, theme checks and overflow assertions |
| API documentation | Exported OpenAPI contains **45 paths** |
| Static quality | Python lint/format, frontend lint/type checks and React component review completed |

The embedded database was PostgreSQL 18.3 through PGlite 0.5.8. It executed the current migrations, seed, schema drift checks, downgrade/upgrade and database history triggers. It validates SQL and types, **not native multi-session concurrency**. A previous revision passed 28 tests against this runtime; that historical result is not represented as a current full-suite PostgreSQL pass. The current 58-test suite was executed on SQLite.

All eight worker commands ran without provider credentials; their purpose was CLI/database/idempotency verification. Network adapters and provider failures have separate fixture coverage. Browser tests replace only the external Greenhouse HTTP transport, so the importer, authentication, API, database and frontend remain real.

## Browser journeys actually exercised

1. Register an independent user; edit Nirma University/B.Tech/CSE, graduation 2028, CGPA 7.38 and India authorization; add Python evidence.
2. Create a manual internship, verify eligibility/score/missing Docker, save it and generate a deadline alert.
3. Record Applied → OA Received → OA Completed → Interview; verify immutable history, dashboard counts and learning recommendations.
4. Generate a digest; visit all primary routes; inspect mobile navigation and capture screenshots.
5. Log into the opt-in demo account, inspect ranked cards and eight clearly synthetic postings, and switch themes.
6. In a separate independent account, create a failing source, inspect the failure, edit its board and retry successfully.
7. Import two occurrences into one canonical job; repeat ingestion with zero new jobs; confirm extracted requirements and move from review-required to eligible.
8. Archive, reimport and confirm the archive persists, then restore explicitly.
9. Save/apply, edit resume metadata, change the password, log out and log back in with the new password.

## Reliability defects fixed in this continuation

- Refresh could revive a manually archived posting; explicit archive metadata now survives ingestion and Restore is available.
- A second board using the same adapter could overwrite primary facts; provenance now records source identity precisely.
- Missing source postings had no reconciliation path; opt-in, repeated healthy snapshots now close individual occurrences conservatively, preserving jobs still active elsewhere.
- Unconfirmed extracted dates could close jobs; eligibility, expiry and reminders now respect date provenance.
- Weekly summaries counted the wrong reporting period; they now report the preceding seven days and distinguish all-time funnel totals.
- Synchronous ingestion database work could block the async API event loop; the route now runs in the threadpool.
- Shared company/skill identity writes could race across users; conflict-safe database inserts handle concurrent discovery.
- Source configuration and resume metadata were not editable; both now have validated API/UI workflows and provenance/history safeguards.
- Password changes and operator recovery were missing; both now revoke existing sessions, preserve exact password text and audit recovery.
- Request size checks trusted headers; actual request streams are now bounded, including chunked input.
- Chained cron stages stopped after a failure; `run-cycle` attempts each stage and reports aggregate failure.
- Optional provider retries now distinguish safe idempotent retries from ambiguous expensive/duplicate POSTs.

Earlier verification also fixed signed-out refresh loops, unstable field labels, overly broad notice parsing, timezone display, SOCKS transport support and stale build reuse. The final browser run used a fresh production build directory.

## Earlier live integration evidence

These checks were executed earlier on 6 October 2026 and were not repeated after this continuation:

| Check | Observed result |
|---|---|
| Live Greenhouse fetch and persistence | 19 records → 16 canonical jobs; zero parse errors; repeat added zero and updated 19 occurrences |
| Live Ashby normalization | 62 records fetched and normalized |
| Live Lever request | Public board returned zero records; nonempty normalization/pagination covered with fixtures |
| Render Blueprint schema | Validated against Render's official JSON schema with zero errors; this continuation changes only the ingestion command to `run-cycle` |

## Supplied gates not executed here

- Native PostgreSQL 17 backend and browser checks are configured in GitHub Actions. A third CI job builds/starts the full Compose stack and checks gateway readiness, seed and worker execution. **Remote CI has not run.**
- Native PostgreSQL could not be started in this local runtime. A temporary Vercel Sandbox request was rejected because no connected CareerOS project ID exists; no sandbox/project was created.
- Docker images were not built locally because there is no Docker daemon.
- No Vercel, Render or Neon resource was provisioned/deployed. No GitHub remote was supplied or pushed. Render access is available, but its tool requires explicit workspace confirmation before selection.
- Resend inbox delivery and credentialed AI extraction were not network-tested. No-key paths and mocked provider retry/error paths passed.
- No production load test, independent security audit, email ownership verification, self-service email recovery, MFA or legal/visa validation is claimed.

## Deployment boundary

The application has been implemented, built and tested locally. To complete hosted delivery: connect the intended GitHub repository, confirm the Render workspace, configure Neon and deployment secrets, run native PostgreSQL/container CI, deploy and execute `DEPLOYMENT.md` smoke checks. Registration can stay closed: create the personal account with the secure operator CLI. Missing source facts remain review items; scores and learning-hour estimates remain transparent heuristics.
