# How CareerOS teaches software engineering

You do not need to understand this entire repository at once. Trace one real user action from the button to the database and back. Read the associated test, change one input, predict the result, then run the test. This builds the understanding you need for an interview instead of memorizing technology names.

## Suggested study order

| Session | Study | Experiment you should be able to explain |
|---|---|---|
| 1 | Eligibility + unit tests | Why does 7.38 pass 7.0 and fail 8.0? What happens when CGPA is missing? |
| 2 | Matching + skill gaps | Change one weight while preserving sum=100 and predict a ranking change |
| 3 | Job REST routes + schemas | Add a posting; inspect request, validation error and response in browser Network tools |
| 4 | SQLAlchemy models + migrations | Follow user → job → application → event and identify each foreign key |
| 5 | Authentication + gateway | Trace login cookies, access expiry, refresh rotation, CSRF and logout |
| 6 | Ingestion + deduplication | Feed one posting twice and explain why one job has multiple occurrences |
| 7 | Application history + analytics | Reject an application after interview and explain why interview conversion remains counted |
| 8 | Worker locks + notifications | Execute a command twice and explain why alert records are not duplicated |
| 9 | Frontend state + browser tests | Save a job and identify which cached queries must be invalidated |
| 10 | CI + deployment + operations | Explain why a successful build is different from a healthy hosted service |

## 1. REST APIs and validation

**What:** `routers/jobs.py`, `routers/profile.py`, `routers/applications.py` expose HTTP resources. `schemas.py` defines their accepted input.

**Why:** Clients need stable boundaries independent of database layout. The browser cannot be trusted to validate correctly or to enforce authorization.

**Flow:** form → `lib/api.ts` JSON request → Next gateway → FastAPI dependency → Pydantic validation → domain/persistence work → JSON response → query-cache refresh.

Examples: `GET /jobs` reads a paginated list; `POST /jobs` creates/upserts; `PUT /jobs/{id}` corrects facts; `PATCH /applications/{id}` records a new application state. Validation yields 422, unauthenticated access 401, forbidden CSRF/origin 403, wrong owner 404 and uniqueness conflict 409.

**Complexity:** Parsing is proportional to body size. Domain work determines most endpoint cost. Input limits prevent unbounded lists/descriptions. Pagination limits the returned page, but ranking still considers the user's full collection.

**Alternative:** GraphQL could let clients select nested fields; it adds query authorization/cost complexity that this small app does not need. Server Actions could simplify some UI writes but would couple the backend more tightly to Next.js.

**Interview questions:** Why validate on the server if you already use Zod? How is PUT different from PATCH here? Why return 404 for someone else's UUID? What makes POST non-idempotent, and why is job upsert an intentional exception?

## 2. PostgreSQL and database design

**What:** `models.py`, `db.py` and `apps/api/alembic/versions` define entities, transactions, indices and schema evolution.

**Why:** Data must survive restarts, preserve relationships and reject invalid concurrent writes. A browser array or localStorage is not a shared private database.

**Flow:** SQLAlchemy creates parameterized queries; PostgreSQL enforces unique constraints and foreign keys; commit makes a transaction durable; rollback discards it.

`applications(user_id, job_id)` is unique, so the same job cannot accidentally become two CRM cards. `application_events` retains every recorded transition. `job_source_occurrences` is a separate entity because one canonical opportunity may have several origins.

**Trade-off:** Stable dimensions are columns; variable extracted requirements are validated JSON. JSON is flexible but harder to index/query than normalized rows. Project evidence lists are small JSON arrays in this V1; explain why this is a deliberate boundary rather than claiming every field is normalized.

**Complexity:** Indexed exact lookups are generally O(log N); joins/select-in loads avoid one query per card. Current in-memory sorting is O(J log J). Measure query counts before changing architecture.

**Practice:** Open `GET /docs`, create a job, find its row, then inspect its skills and occurrence rows. Change a model only after understanding how to create/review a migration. On a disposable database, apply both migrations and try modifying an event: the trigger rejects it.

**Interview questions:** What is a foreign key? What race does a unique constraint prevent? Why isn't checking existence in Python enough? How do you deploy a new nullable column safely? What is the difference between an index and a constraint?

## 3. Authentication, sessions and CSRF

**What:** `security.py`, `routers/auth.py`, the Next `/api/[...path]` route and `lib/api.ts`.

**Why:** Only the owner should access private profiles and applications. Storing a user ID in the browser is not authentication.

**Flow:** registration hashes the password with Argon2id; login verifies it, generates random secrets and stores token digests; the browser receives cookies. Every request resolves the access digest to a non-expired session. A mutation must also prove the CSRF token. Refresh rotates secrets. Logout revokes the database session.

Hashing differs from encryption: there is no password decryption key. Password hashes intentionally cost memory/time; token digests can use fast SHA-256 because tokens already have high entropy.

**Trade-off:** Opaque sessions require a database lookup but support immediate revocation. JWTs can avoid some lookups but complicate revocation and rotation. Same-origin proxying simplifies browser cookie behavior across Vercel/Render, at the cost of one server hop.

**Complexity:** Token lookup uses unique indexes. Argon2 intentionally dominates login CPU/memory. Shared rate buckets stop rapid guessing; do not optimize away password-hashing work.

**Practice:** Inspect HttpOnly/Secure/SameSite in DevTools. Remove the CSRF header and predict 403. Expire access in a test and explain why refresh can still work. Read `test_auth_cookie_rotation_csrf_and_logout`.

**Interview questions:** Why doesn't HttpOnly alone prevent CSRF? Why not store tokens in localStorage? Why rotate refresh tokens? Why is an email address not proof that you own the email? Which production account-recovery features are still missing?

## 4. Job ingestion and the adapter pattern

**What:** `services/sources.py` and `services/ingestion.py`.

**Why:** Vendor APIs have different field names and failure modes. Ranking should understand one normalized job schema.

**Flow:** fetch vendor JSON → normalize one record → validate `JobIn` → savepoint → deduplicate/upsert → preserve raw occurrence → commit run health. A malformed record rolls back only its savepoint; a failed board does not cancel later boards.

**Algorithms:** bounded pagination, exponential backoff, field normalization, set-based skill extraction. Three fetch attempts bound network work; the response-size cap bounds memory. Dedup's conservative fallback compares titles inside the same company/location/type candidate set.

**Trade-off:** A public JSON feed is more stable and auditable than scraping arbitrary HTML. Manual entry is a useful product feature when automation is inappropriate. Async network I/O allows waiting without occupying the entire process; the database remains synchronous for simpler transactions.

**Practice:** Add a fake raw posting to `test_sources.py`. Remove its title and observe a parse error without losing the valid neighboring record. Simulate a 503 twice then 200; explain the retry schedule.

**Interview questions:** Adapter vs inheritance? Why retain the raw payload? When should 404 not be retried? Why is a source's empty response different from a closed job? Why are retries dangerous for writes without idempotency?

## 5. Deduplication and identity

**What:** `services/repository.py`: `identity`, `normalized_url`, `upsert_job`.

**Why:** A job discovered twice must not inflate your opportunity count or produce duplicate reminders.

**Flow:** resolve exact occurrence → canonical identity → conservative cross-source comparison → create or update one canonical row → attach/update occurrence. Requisition ID outranks fuzzy title similarity. Tracking parameters do not change a job's URL identity.

**Algorithms:** SHA-256 compresses canonical identity into a fixed key. It does not make the inputs correct; domain choices define identity. SequenceMatcher provides a narrow fallback, not a guarantee. Distinct requisitions remain separate even when job titles match.

**Complexity:** Indexed identity lookup is cheap; the fuzzy fallback scans eligible company candidates and compares strings. For a very large board, add blocking/index strategies instead of comparing every pair.

**Trade-off:** Aggressive fuzzy merging removes true distinct roles; conservative merging leaves some duplicates. Preserving occurrences and supporting human correction is safer than silently destroying source records.

**Interview questions:** Why isn't company+title always unique? What does a hash collision mean? How is a natural key different from a UUID? How do locks and constraints complement one another?

## 6. Deterministic eligibility and matching algorithms

**What:** `eligibility.py`, `matching.py`, `test_domain.py`.

**Why:** Arithmetic facts should not depend on model wording. A high skill overlap must not override a wrong graduation year.

**Flow:** hard-rule engine → explain state → calculate eight weighted factors → suppress blocked scores → classify action → compute missing skill sets → aggregate learning priorities.

Use sets: required∩known gives overlap, required−known gives gaps. Project technologies alone never count as evidence. Requirements extracted by an LLM/rules remain review-required until confirmed.

**Complexity:** Membership/set operations are average O(1) each, so overlap/gap work is linear in inputs; sorting recommendations adds O(K log K). Eight fixed factors are O(1) apart from their membership inputs.

**Trade-off:** Rules are explainable but need explicit aliases and cannot infer every degree equivalence. Weights and learning effort are heuristics, not hiring probabilities. A black-box recommendation would need evaluation data before being trusted.

**Practice:** Write one test each for exact threshold, missing fact and conflicting requirement. Ask why preferred Docker cannot disqualify an otherwise eligible student. Add the Docker skill and predict which gaps disappear.

**Interview questions:** Why evaluate eligibility first? What's the difference between unknown and false? Why does ranking need a version? When is ML useful here, and which decisions should stay deterministic?

## 7. Application history and funnel analytics

**What:** `routers/applications.py`, `services/analytics.py` and append-only migration `8f22a1`.

**Why:** Current status alone destroys history. A rejected candidate may still have passed an OA and interviewed.

**Flow:** status edit → validate ownership/resume → lock row → update current state → append event → commit → aggregate historically reached milestones.

The application row answers “where is it now?” Events answer “how did it get here?” This is a small audit-history pattern, not full event sourcing. Notes changed without a status change also create a history entry.

**Complexity:** O(A × E) in the in-memory V1 aggregation, where A is application count and E events/application. Database-side milestone aggregation can replace it when needed.

**Trade-off:** Users may skip stages because companies skip them. Do not invent an OA event just because an interview happened. Rates are conditional on recorded data and pending outcomes. A sample under 10 applications cannot justify a confident bottleneck diagnosis.

**Interview questions:** Why not just count current OA_COMPLETED rows? What is an immutable log? How do you correct a mistake without rewriting history? Why aren't correlations proof of resume quality?

## 8. Background jobs, locks and notifications

**What:** `apps/worker/worker/__main__.py`, `services/locking.py`, `services/notifications.py`.

**Why:** Polling job boards and sending digests should happen independently of someone keeping the browser open.

**Flow:** deployment cron runs command → acquire command lock → process source/user services → commit notification records → optional delivery → record success/failure. Duplicate commands skip if a lock is held. A unique notification key prevents repeat alerts for the same event/day/threshold.

**Trade-off:** A cron CLI is simpler than Celery/Redis for personal scale. It has finite work and clear exit codes. A queue becomes useful for high fan-out, independent retries and continuously arriving work; business services are already separate from orchestration.

A PostgreSQL session advisory lock requires a dedicated stable connection; transaction-pooling endpoints can release/switch sessions and break the assumption. That is why deployment requires the direct Neon endpoint. SQLite uses an OS process lock only in local Linux/macOS development.

**Email:** record notifications first. Resend is optional, user opt-in is required, and delivery uses an idempotency key. Inbox delivery cannot be guaranteed just because a request returned successfully.

**Interview questions:** At-most-once vs at-least-once vs exactly-once? Why use both lock and unique key? What if a process crashes after sending but before committing? How does backoff prevent retry storms?

## 9. Frontend, accessible UI and state

**What:** `components/workspace.tsx`, feature components, `components/ui.tsx`, `lib/api.ts` and App Router routes.

**Why:** A useful tool needs loading, error, empty and success states as well as happy-path cards. Scoring belongs on the server to avoid duplicated truth.

**Flow:** route → authenticated workspace → TanStack query → API payload → typed presentation. Mutations invalidate cached views. Dialogs use native `<dialog>` focus behavior; inputs have labels, hints and validation. CSS adapts sidebar/cards/tables to mobile and respects reduced motion.

**Trade-off:** Client-side fetching suits this private interactive dashboard; SEO is not the goal. Dynamic imports split feature screens. A same-origin gateway adds server work but avoids exposing credentials or cross-site session cookies.

**Practice:** Use browser Network to see a save request and its refreshes. Disconnect the API to see a real error. Navigate with the keyboard, then test at 390px and in light theme. Understand the signed-out refresh-loop regression and why a retry cannot restart the same failed query forever.

**Interview questions:** What is cache invalidation? Why shouldn't a form's help text accidentally become its accessible name? Why is client-side hiding not authorization? What causes a hydration mismatch?

## 10. Testing, CI/CD and operations

**What:** `tests`, `.github/workflows/ci.yml`, Dockerfiles, `render.yaml`, `docs/VERIFICATION.md`.

**Why:** A compiling app can still be unusable; a passing mock can still conceal integration failures. Tests need layers.

- Unit tests isolate pure rules and edge cases.
- API integration tests exercise auth, validation, persistence and ownership together.
- Source fixtures test shape/retries without relying on a changing website.
- Browser tests exercise registration through application progression and responsive navigation.
- Live source checks confirm an integration at a point in time.
- CI repeats critical checks on a clean machine and native PostgreSQL.

**Trade-off:** End-to-end tests give broad confidence but are slower and more brittle than pure tests. Use precise user-facing locators; inspect traces and logs on failure. Do not “fix” a failed test by deleting the assertion that uncovered a bug.

**Deployment flow:** Git commit → CI → backend migration/service release → frontend release → readiness/smoke check. Environment variables provide secrets separately from code. Structured request IDs connect UI errors to backend logs. A health check and a readiness check answer different questions.

**Interview questions:** Why test PostgreSQL if SQLite tests passed? Why should migrations run once per release? How can a rollback conflict with a new schema? What would you monitor? Which operations are idempotent? How would you diagnose a 502 from the gateway?

## Explain CareerOS in a viva

“CareerOS ingests public or manually entered job postings into a canonical database. It checks hard eligibility against my editable profile before calculating an explainable weighted score. It preserves source evidence, tracks application events and uses relevant skill demand to prioritize learning. A separate scheduled CLI reuses the same services for ingestion and alerts. The UI is a Next.js workspace over an authenticated FastAPI backend. I chose deterministic rules for factual decisions, a relational database for integrity, and cron rather than a queue because the workload is initially personal scale.”

Then demonstrate one difficult case, such as CGPA 7.38 vs requirement 8.0, and one operational case, such as a failed source leaving other sources healthy. Be candid about heuristic parsing, manual visa research, account-recovery limitations and what has actually been deployed.

## 11. Reliability lessons from completing V1

Read `test_reliability.py`, `test_migrations.py` and `tests/e2e/ingestion.spec.ts` alongside the implementations. These are regression tests for meaningful failures discovered during review.

**One job, several occurrences.** A canonical opportunity can appear on two boards. Model availability per occurrence, then close the canonical job only when none remain active. Missing is not necessarily closed: an empty or partially broken feed is weak evidence. Requiring repeated healthy snapshots makes that assumption explicit and configurable. A user's deliberate archive is separate metadata and survives automated refresh.

**Uncertainty must survive the entire workflow.** Marking AI output unconfirmed in a parser is insufficient if an expiry worker later trusts that date. Trace a deadline through parsing, provenance, eligibility, reminders and expiry. Human confirmation must change the same fact used by all those consumers.

**Locks and unique constraints solve different problems.** A per-user writer lock serializes deduplication and edits for one workspace. A global company or skill can still be discovered by two different users at once. Atomic conflict-safe insertion handles that shared identity without broad global locking. SQLite and embedded PostgreSQL checks do not prove native multi-session behavior; native PostgreSQL CI is a separate gate.

**Retry depends on consequences.** GET source fetches can usually be retried after transport errors. A POST may have succeeded before its response was lost. Resend retries reuse an idempotency key; optional AI calls avoid automatic retries after ambiguous failures. Read `outbound.py` and compare the tests for 429, server errors and transport failures.

**Time windows are product requirements.** A Monday weekly summary should include the preceding seven days, not start counting from that same Monday. Dashboard funnel totals and recent application activity are different metrics. Explicit labels and boundary tests prevent plausible but misleading reports.

**Migrations are executable code.** Metadata-created test tables omit migration triggers. The migration test installs the real schema, seeds data, proves history cannot be rewritten and checks retention across downgrade/upgrade. `/ready` verifies the exact schema revision the deployed application expects; `/health` only verifies the process responds.

**Test the whole user action.** The third browser journey starts with a failed source, edits it, ingests two occurrences into one job, confirms uncertain facts, archives/reimports/restores, records an application, edits resume metadata and changes credentials. Only the remote feed is replaced. This catches route/form/cache/integration failures that isolated mocks miss.

**Practice:** Run `scripts/verify-browser.sh`, read one failure trace, then run `python -m worker run-cycle` twice against a disposable database. Explain why duplicate notifications are prevented and why a failed ingestion stage should not suppress all deadline alerts. Never point destructive test fixtures at personal or production data.

## 12. Turning a manual importer into an automatic service

Read `services/discovery.py` and `test_discovery.py`. Automatic discovery adds an execution trigger and persisted scheduling state around the existing importer instead of duplicating it. An API lifespan starts a background thread, keeping blocking database operations away from the HTTP event loop. A per-user lock ensures two API processes or a CLI worker cannot run the same discovery simultaneously.

The database records next-run time, pause state and last results. Restarting the app does not forget a pause or run early; an interrupted due run can be retried once the old process releases its OS/database lock. Source bootstrapping checks existing board identity and preserves disabled sources. Internet failures become visible partial status with a shorter retry interval, while valid imports survive.

The ten-board catalog supplies dependable starter coverage. Optional Brave Search adds rotating category/country queries, with original-source verification before import. Unsupported results remain review leads. The title filter admits technical and product-design early-career titles; the eligibility engine still handles missing and unconfirmed requirements conservatively. Live source checks confirm actual payload compatibility, and a browser test proves that a user receives jobs without first configuring a source.
