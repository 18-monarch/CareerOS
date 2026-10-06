# Deploy CareerOS

Target: Vercel frontend + Render FastAPI/cron + Neon PostgreSQL. Repository preparation and configuration are complete; no cloud deployment or billable resource was created during implementation.

## 1. Push the repository

Create a **private** GitHub repository, then from this checkout:

```bash
git remote add origin https://github.com/YOUR_ACCOUNT/CareerOS.git
git push -u origin main
```

Preserve the included Git history. Do not upload `.env`, databases, virtual environments or `node_modules`. The zip excludes these. Configure repository branch protection to require all three CI jobs after they have run once.

## 2. Neon

Create a PostgreSQL database and a least-privilege application role. Record the **direct**, TLS-enabled connection string, e.g. `postgresql+psycopg://USER:PASSWORD@DIRECT_HOST/DB?sslmode=require`. Avoid the `-pooler` hostname: session-scoped advisory locks require a stable physical session. Use a separate disposable database for CI.

Keep database region close to Render (the Blueprint uses Singapore). Enable backups/restore according to your chosen plan and test restoring before storing valuable application history. Vercel never receives database credentials.

## 3. Render backend

Apply `render.yaml` to the private repository or create its services manually. The Blueprint was checked against Render's official JSON schema; provisioning itself still requires your account. Review current service/cron pricing before applying it.

Supply the `careeros-production` environment group values:

- `DATABASE_URL`: direct Neon URL with `sslmode=require`.
- `FRONTEND_ORIGIN`: exact final Vercel/custom-domain HTTPS origin, no trailing slash.
- `COOKIE_SECURE=true`, `ENVIRONMENT=production`.
- `REGISTRATION_ENABLED=false` by default; use the operator CLI below to create your personal account.

Build: `pip install -r requirements.lock && pip install --no-deps .`

Pre-deploy: `alembic upgrade head`

Start: `uvicorn careeros.main:app --host 0.0.0.0 --port $PORT`

Health check: `/ready`. `/health` only proves that the process is alive; `/ready` also verifies migration state and database access.

The included starter plan supports pre-deploy migrations. For a plan without pre-deploy support, run the migration manually through the service shell before starting the new version. Never launch multiple independent migration processes at once.

## 4. Vercel frontend

Import the same repository. Root Directory: `apps/web`. Framework: Next.js. Node: 24. Install: `npm ci`. Build: `npm run build`.

Set server-side variables:

```text
API_BASE_URL=https://YOUR_RENDER_API.onrender.com
FRONTEND_ORIGIN=https://YOUR_FRONTEND.vercel.app
```

Set the exact same frontend origin on Render. Redeploy after changing environment variables. Do not prefix these with `NEXT_PUBLIC_`; the browser talks only to `/api` at its own origin. Cookies are set on that origin through the Next.js gateway and stay HttpOnly except for the random CSRF token.

Preview domains are intentionally not wildcard-trusted. Use a separate staging backend/database and set that preview origin explicitly if you need preview testing.

## 5. Initialize your account

Choose one path:

- Recommended: run `python -m careeros.manage create-user --email your@email.example --name "Your name"` in the backend shell. Enter a password at the hidden prompt. This creates an empty account while registration stays closed.
- Alternatively enable registration briefly, create an account in the UI, then disable registration.
- For a private demo only: run `DEMO_PASSWORD='unique-password' python -m careeros.seed --email your@email.example` in the backend shell. This adds eight synthetic postings and editable self-assessments. Never use the test password from CI for a hosted account.

For trusted-operator recovery, run `python -m careeros.manage reset-password --email your@email.example`. The CLI prompts securely, revokes sessions and writes an audit record. Users can also change their password in My profile with their current password.

No default admin password is installed. Users can manage only their own sources; there is no cross-user public admin dashboard.

## 6. Scheduled jobs

All schedules in `render.yaml` use UTC:

| Service | Schedule | India time | Commands |
|---|---|---|---|
| Ingestion | `15 */6 * * *` | 05:45, 11:45, 17:45, 23:45 IST | `run-cycle`: ingest, recalculate, expire, deadline alerts |
| Daily | `30 2 * * *` | 08:00 IST | deadline alerts, digest |
| Weekly | `30 2 * * 1` | Monday 08:00 IST | weekly summary |

The scheduler must be deployed separately; merely running the API does not start cron. All cron services use the same environment group and direct database endpoint. Advisory locks skip duplicate runs. Alert unique keys make repeated invocations safe.

Connect actual source boards in the UI. Demo jobs are not a source of live opportunities. `refresh-jobs` is the same fetch/update pipeline as ingestion and is useful for a separately scheduled refresh cadence if desired.

## 7. Optional providers

Email: configure a verified sender, `RESEND_API_KEY` and `EMAIL_FROM` on the shared backend/cron group. Turn on email in the account profile. In-app notification creation remains independent of delivery. Failed deliveries stay visible and retry on later runs.

AI: set `AI_API_KEY`, `AI_MODEL`, and an operator-controlled `AI_BASE_URL` compatible with chat completions. Only pasted job descriptions are sent for optional extraction. No resumes, passwords or full profiles are sent. Output is Pydantic-validated and marked unconfirmed; failures use local parsing.

Official feeds: set `ALLOWED_FEED_HOSTS` to trusted domains. This is a permission list, not a wildcard. Use documented public JSON rather than arbitrary web scraping.

## 8. Post-deployment smoke check

1. `/health` and `/ready` return 200, and `/ready` shows the expected Alembic head.
2. Register/login from the final frontend URL; verify Secure/HttpOnly cookies and logout.
3. Edit graduation/CGPA; import a source; inspect raw requirements and provenance.
4. Save a role, mark Applied then OA Received, reload and verify the event history.
5. Run deadline/digest cron manually twice; verify no duplicate records.
6. Confirm a second user cannot read the first user's job/application URL.
7. Check desktop/mobile navigation, error states and Render logs with request IDs.
8. Send a test email if email is configured; verify sender/domain delivery rather than assuming API acceptance equals inbox placement.

## Operations

JSON logs contain request IDs, route, status, latency, source ID and error class. They omit bodies, credentials and tokens. Record run counts via source health. Monitor `/ready` externally. Keep logs/retention appropriate for a personal app.

Rollback frontend/backend code via platform deployments only after checking database compatibility. Database migrations are a separate concern. Take a Neon backup/branch before destructive changes. The three migrations (current head `c61f03`) add tables, immutable-history triggers and source-reconciliation columns; review their explicit downgrade paths. `/ready` requires the exact head shipped with the API. Update that expected revision alongside future migrations.
