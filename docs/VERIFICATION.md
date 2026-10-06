# Engineering verification report

Verification date: 6 October 2026. This report distinguishes executed checks from provided configuration. No cloud deployment is claimed.

## Executed and passed

| Check | Result / evidence |
|---|---|
| Backend unit/integration suite | 36 tests passed on SQLite; eligibility, ranking, parsing, deduplication, auth/CSRF/rotation, ownership, persistence, application history, job corrections and supporting modules |
| PostgreSQL SQL/type compatibility | 28 tests passed against PostgreSQL 18.3 via PGlite 0.5.8; one multi-session workflow deselected because PGlite multiplexes a single backend session |
| Database migrations | Initial relational migration and append-only event migration applied on SQLite and embedded PostgreSQL; head `8f22a1` |
| Schema drift | `alembic check`: no new upgrade operations detected |
| Immutable history | An UPDATE against a migrated SQLite application event was rejected by the database trigger; fixture transaction rolled back |
| Worker CLI | All seven commands executed locally without errors; repeat digest/deadline generation does not duplicate notification keys |
| Live Greenhouse fetch + persistence | 19 source records; 16 canonical jobs after deduplication; 0 parse errors; repeat run added 0 and updated 19 source records |
| Live Ashby normalization | 62 records fetched and 62 normalized after fixing an overly broad label parser |
| Live Lever request | Public test board responded with 0 records; normalization/pagination exercised with fixtures, not a nonempty live board |
| Frontend lint and TypeScript | Clean checks on authored source |
| Frontend unit tests | 5 component tests passed; they cover decision labels, demo markers, functional actions, disabled saved state, empty/errors and accessible field labels |
| Production build | Next.js 16.3.8 production build succeeded; App Router pages and same-origin gateway compiled |
| Browser workflow | 2 Playwright/Chromium tests passed; complete workflow test and seed/theme/responsiveness test |
| Desktop/mobile visual check | Captured and inspected 1280px desktop and 390px mobile screenshots; no horizontal overflow in checked views |
| Primary navigation | All workspace routes visited in E2E; no framework error overlay or uncaught page errors in core flow |
| Render Blueprint | Validated against `https://render.com/schema/render.yaml.json`: 0 schema errors |
| API documentation | OpenAPI exported to `packages/shared/openapi.json`; 42 API paths |

The PostgreSQL migration/schema check used an embedded PostgreSQL runtime after the environment prevented installing a native system server. It validates PostgreSQL SQL and types, not production concurrency. The supplied GitHub Actions workflow runs the full backend suite, migrations, seed and workers on native PostgreSQL 17. That remote CI workflow has not been executed in a GitHub repository here.

## Browser journey actually exercised

1. Register a new independent user and authenticate through the real frontend gateway.
2. Save Nirma University, B.Tech/CSE, graduation 2028, CGPA 7.38 and India authorization.
3. Add Python self-assessment and create an internship with graduation/CGPA requirements and a near deadline.
4. Open its detail view; see ELIGIBLE, score breakdown and missing preferred Docker.
5. Save the role, generate and observe the deadline alert.
6. Record Applied → OA Received → OA Completed → Interview.
7. Verify all five history entries, dashboard milestone counts and Docker learning recommendation.
8. Generate digest, visit every primary route, navigate on mobile, check overflow and capture screenshots.
9. Separately log into the opt-in demo seed account, inspect four ranked dashboard cards and eight synthetic postings, and switch dark/light themes.

## Defects found and fixed during verification

- Initial signed-out requests could cause a refresh/cache retry loop. Refresh now requires a CSRF cookie and expiry handling no longer clears/recreates the identity query repeatedly.
- Form help text and select option text polluted accessible labels. Controls now use stable explicit `htmlFor` IDs and separate descriptions.
- Long prose containing “company:” or “role:” could be misread as a notice header and fail normalization. Extraction now requires a line-start label and bounded value; all 62 sampled Ashby records normalize.
- Outbound HTTP clients needed SOCKS support in this environment. The required optional transport dependency is now included.
- Datetime-local editors originally reused raw UTC text. Values now convert to local time before display; OA/interview inputs normalize to UTC on the server.
- Human-reviewed job facts can be corrected through a dedicated endpoint/UI while retaining raw occurrences; automatic refresh preserves those corrections.
- Dashboard cards now carry saved/application state, preventing duplicate Save actions. Its next application deadline excludes applications already submitted or concluded.
- A reused build directory served stale JavaScript during a final rerun. Rebuilding into a fresh `.next-release` directory resolved it; the final production build and both browser tests passed together. Generated build directories are excluded from the repository/archive.

## Not executed / not claimed

- No Vercel, Render or Neon resource was provisioned or deployed. No GitHub remote was supplied or pushed.
- Native PostgreSQL multi-session concurrency and Neon pooled/direct endpoint behavior were not exercised locally; CI and deployment smoke checks are provided.
- Docker images/Compose were authored but not built here because the runtime has no Docker daemon.
- Resend delivery and optional OpenAI-compatible extraction were not network-tested with real credentials. In-app/no-key paths work.
- Browser QA used a portable Chromium via Playwright after the standard browser download and agent-browser daemon were unavailable. This is real browser automation, not a screenshot mockup.
- No public-production load test, independent penetration test, email ownership verification, self-service recovery, or legal/visa validation is claimed.

## Deployment readiness boundary

This is a functioning, locally verified personal CareerOS V1 with deployment configuration. Before external use: provide actual secrets, run native PostgreSQL CI, deploy to your accounts, close registration after creating your account, and execute `DEPLOYMENT.md` smoke checks. Treat missing source facts as review items. Treat matching scores and learning-hour estimates as transparent heuristics.
