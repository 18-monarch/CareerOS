# Deploy CareerOS: Netlify + Render + Neon

**Free discovery option:** follow [DEPLOY-FREE.md](../DEPLOY-FREE.md) to run discovery in GitHub Actions with a manually created Free Render API. The Blueprint instructions below include an optional paid Render cron.

Start with [DEPLOY-MANUALLY.md](../DEPLOY-MANUALLY.md) for the complete Windows-friendly walkthrough. The files are prepared and tested locally; no cloud services have been created by this delivery.

## 1. Repository and cost

Create an empty **private** GitHub repository named `CareerOS`, without a generated README, license or `.gitignore`. Push the included history from the `careeros` folder:

```powershell
git remote add origin https://github.com/YOUR_ACCOUNT/CareerOS.git
git push -u origin main
```

If `origin` already exists, inspect `git remote -v` and use the correct existing remote rather than overwriting it. Keep all environment files, local databases and dependency folders out of Git. Wait for CI to pass before deploying. The Blueprint uses `checksPass` for subsequent automatic deployments.

The proposed Blueprint creates **one Free API service and one Starter cron service**. Render cron has a $1/month minimum per service and is billed by active running time; this is not a fixed total project price. Netlify, Neon, search and email have independent plan/usage limits. Review billing before applying. Upgrade the API to an always-on paid instance when cold starts are no longer acceptable. Free API inactivity does not stop the separate cron job.

## 2. Neon database

Use a separate CareerOS project, preferably in Singapore to match Render. Do not repurpose another project's database. Choose PostgreSQL 17 (the native CI target) and retain your plan's backup/restore settings.

Copy the **direct** connection URL with TLS, not the hostname containing `-pooler`:

```text
postgresql+psycopg://USER:PASSWORD@DIRECT_HOST/DB?sslmode=require
```

This app uses session-scoped advisory locks and therefore deliberately requires direct connections for API and workers. Store it as `DATABASE_URL` in Render, never Netlify or client-side code. Existing local SQLite data is not uploaded automatically; keep your local database backup. Cloud onboarding starts with an empty account unless a separate reviewed data migration is performed.

## 3. Reserve the frontend address

In Netlify, import the private repository and choose a stable project name. Root `netlify.toml` specifies:

| Setting | Value |
|---|---|
| Base directory | `apps/web` |
| Build command | `node scripts/check-hosted-env.mjs && npm run build` |
| Publish directory | `.next` |
| Node version | `24` |

Use Netlify's automatic Next.js adapter, not static ZIP drag-and-drop or `next export`. Record the actual assigned HTTPS address, such as `https://YOUR_NAME.netlify.app`. There is no guaranteed reserved name in this package. The first build intentionally fails until the two environment variables below are set.

## 4. Render API and worker

Create a Blueprint from the CareerOS Git repository using root `render.yaml`. Confirm the two services and charges before Apply. Supply the shared group values:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Direct Neon URL with TLS |
| `FRONTEND_ORIGIN` | Exact Netlify/custom-domain HTTPS origin, no trailing slash |

The Blueprint supplies production mode, secure cookies, closed registration, Python 3.12.14, a six-hour discovery interval, `AUTO_DISCOVERY_ENABLED=false`, and `EXTERNAL_DISCOVERY_ENABLED=true`.

Both services install locked Python requirements. Their explicit entry points are:

```text
API:  python -m careeros.deploy api
Cron: python -m careeros.deploy cron
```

These entry points acquire a migration lock, upgrade using the active database connection and then start their workload. They work without Render's paid pre-deploy or shell features. Concurrent schema upgrades wait up to 45 seconds, then fail visibly rather than running overlapping migrations. Keep only reviewed, backwards-compatible migrations in automatic deployments; branch and test before destructive changes.

The API binds `0.0.0.0:$PORT`; health check `/ready` requires schema `e91a05` and a working database. The worker runs at `15 * * * *` UTC, which is **:45 past every hour in India**. It expires old records and sessions, bootstraps starter boards, processes due discovery/research, prepares enabled drafts and generates/delivers alerts. Healthy users become due six hours after completion, so actual checks occur at the next hourly tick (roughly six to seven hours apart). A queued manual check waits for the next worker tick. Failed scans become due again after one hour. Notifications/digests are deduplicated; this setup does not promise a fixed 08:00 digest time.

Do not enable the old ingestion/daily/weekly services alongside this Blueprint. For an already deployed older Blueprint, review Render's proposed removals rather than deleting unknown services. No existing unrelated services were changed here.

## 5. Finish Netlify configuration

Set these in Netlify's environment-variable UI, available to **builds and functions**:

```text
API_BASE_URL=https://YOUR_RENDER_API.onrender.com
FRONTEND_ORIGIN=https://YOUR_NAME.netlify.app
```

Use the API URL Render actually assigned. Redeploy Netlify after setting these. `FRONTEND_ORIGIN` must exactly match Render's value. Never prefix these with `NEXT_PUBLIC_`, and never put database/search/email keys in Netlify. The browser uses its same-origin `/api` gateway, preserving separate Secure cookies and CSRF protection.

The build validates HTTPS origins and rejects missing settings. Netlify's deployment-context variables are build-only, so the Next.js configuration embeds only non-secret platform/context labels. The gateway disables account access on deploy previews and branch deploys. Use the production URL for private beta testing. A separate staging backend/database and reviewed configuration are required before enabling preview account access.

Free Render services may take about a minute to wake. The Netlify gateway returns a controlled error after 25 seconds; wait and retry. Queued discovery runs independently on the cron service.

## 6. Create your private account

Registration stays disabled. After the Render API has migrated the Neon database, run this from your installed CareerOS environment:

```powershell
.\.venv\Scripts\python.exe -m careeros.cloud_account
```

The helper prompts for the direct TLS database URL and password without echoing them, validates the schema, and creates an empty account. It does not edit local environment files or overwrite an existing account. The root manual guide includes dependency setup. Trusted operators can still use `careeros.manage` for password recovery with the intended database configured.

Sign in through the Netlify URL. Complete your real education, work authorization, categories, skills, projects, portfolio and resume. The first worker run will connect starter sources automatically.

## 7. Search and email

Add optional provider values to the **shared Render environment group**, so both API and cron receive them:

- `BRAVE_SEARCH_API_KEY`: broad web research. Without it, ten public feeds and direct link inspection still work.
- `RESEARCH_QUERY_LIMIT=4`, `RESEARCH_RESULT_LIMIT=12`: bounded per-user searches; provider usage depends on enabled users and retries/manual checks.
- `RESEND_API_KEY`, `EMAIL_FROM`: verified email sender. Enable email in your profile and test actual delivery. No credentials means in-app notifications only.

Redeploy affected services after changes. The application runner remains local and standard-Lever-only. Hosted discovery can prepare packets, but does not launch browser submissions. The runner must connect to the cloud account's database to see its approved queue; a local SQLite runner cannot see cloud approvals. A managed cloud application runner is a later deployment step.

## 8. Verify the live system

From a Python environment with the project installed:

```text
python scripts/check-deployment.py --url https://YOUR_NAME.netlify.app
```

This read-only smoke check verifies page availability, readiness through the gateway, unauthenticated account protection, cross-origin mutation rejection and no-cache responses. It sends no applications and creates no records.

Then manually verify login/logout, profile persistence after reload, PDF upload, category brief, one scheduled discovery run with real source counts, queue/pause/resume, notification deduplication, and a test email if configured. Confirm the Next.js adapter's deployed cookie handling on the actual host. Review Render logs and cron exit status. Native PostgreSQL CI and hosted end-to-end verification are required release gates; an embedded database test does not establish multi-session behavior.

## References

- https://docs.netlify.com/build/frameworks/framework-setup-guides/nextjs/overview/
- https://docs.netlify.com/build/configure-builds/monorepos/
- https://docs.netlify.com/build/functions/environment-variables/
- https://render.com/docs/free
- https://render.com/docs/cronjobs
- https://render.com/schema/render.yaml.json
