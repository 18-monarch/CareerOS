# CareerOS: deploy without a paid Render cron

Use Netlify for the website, one **Free Render Web Service** for the API, Neon for PostgreSQL, and **GitHub Actions** for scheduled discovery. Choose free plans and stay within their limits. This is a personal-project setup with cold starts and best-effort scheduling, not an uptime guarantee.

Standard GitHub-hosted runners have no minute charge for public repositories. Private repositories have a monthly included allowance shared with CI. This workflow uses a standard Ubuntu runner, creates no artifacts or caches, and starts disabled until you opt in.

## 1. Update your project

Merge the free-discovery change after its CI checks pass, then run in your local `careeros` folder:

```powershell
git switch main
git pull --ff-only origin main
```

The older `render.yaml` still describes the optional **paid** Render cron setup. **Do not apply that Blueprint for this free route.** If you already provisioned `careeros-discovery`, disable Blueprint auto-sync and remove that paid service from the Blueprint before deleting only that CareerOS cron service. Removing a resource from YAML alone does not stop billing. Do not delete unrelated services or the database. Use only one discovery scheduler.

## 2. Prepare Neon and Netlify

Create or reuse your dedicated CareerOS Neon project (PostgreSQL 17, Singapore if available). Copy its full **direct** connection URL with `sslmode=require`; turn connection pooling off. The hostname must not contain `-pooler`. Keep this URL private.

Import `18-monarch/CareerOS`, branch `main`, into Netlify and record its actual production HTTPS address. Build settings from `netlify.toml`:

- Base directory: `apps/web`
- Build command: `node scripts/check-hosted-env.mjs && npm run build`
- Publish directory: `.next`
- Node: `24`

The first frontend build can fail until the API environment variables in step 4 exist.

## 3. Create the free Render API manually

Choose **New → Web Service**, connect CareerOS, and enter:

| Setting | Value |
|---|---|
| Name | `careeros-api` |
| Branch | `main` |
| Region | Singapore (match Neon when possible) |
| Language/runtime | Python 3 |
| Root directory | Leave blank |
| Build command | `pip install -r requirements.lock && pip install --no-deps .` |
| Start command | `python -m careeros.deploy api` |
| Instance type | **Free** |
| Health check path | `/ready` |
| Auto-deploy | After CI checks pass |

Add the following environment variables before deploying:

| Name | Value |
|---|---|
| `DATABASE_URL` | Your private direct Neon URL |
| `FRONTEND_ORIGIN` | Actual Netlify production HTTPS origin, no trailing slash |
| `PYTHON_VERSION` | `3.12.14` |
| `ENVIRONMENT` | `production` |
| `COOKIE_SECURE` | `true` |
| `REGISTRATION_ENABLED` | `false` |
| `AUTO_MIGRATE_LOCAL` | `false` |
| `AUTO_DISCOVERY_ENABLED` | `false` |
| `EXTERNAL_DISCOVERY_ENABLED` | `true` |
| `DISCOVERY_INTERVAL_HOURS` | `6` |
| `DISCOVERY_WORKER_INTERVAL_MINUTES` | `60` |

Deploy. The start command applies database migrations under a lock and binds the port Render provides. Once live, open the actual API address plus `/ready`; expect HTTP 200 and schema `e91a05`. No Render Cron Job, Background Worker, paid pre-deploy command or shell is required.

Free Render services sleep after inactivity and share a workspace allowance (including any other free projects you have). A sleeping API can take about a minute to wake. Check current usage and spending settings rather than upgrading when prompted.

## 4. Connect Netlify

Set these Netlify environment variables for **builds and functions**, then redeploy:

| Name | Value |
|---|---|
| `API_BASE_URL` | Actual Render API HTTPS origin, no trailing slash |
| `FRONTEND_ORIGIN` | Same Netlify production origin used on Render |

Use the production site URL. Preview URLs intentionally block account access. A first request to a sleeping API may time out; wait a minute and retry.

## 5. Create your cloud account

From your local project folder, prepare/update the Python environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m careeros.cloud_account
```

Skip the first line if you already have a working Python 3.12 `.venv`. The helper privately prompts for the direct Neon URL, your email/name, and a new password (12+ characters). It does not overwrite an existing account or copy your local SQLite data. Sign in on Netlify and complete your profile, preferred categories, project evidence and resumes.

## 6. Enable GitHub discovery

In the CareerOS GitHub repository, open **Settings → Secrets and variables → Actions**.

In **Secrets → New repository secret**, add:

| Secret name | Value |
|---|---|
| `CAREEROS_DATABASE_URL` | The same direct Neon URL as Render's `DATABASE_URL` |

In **Variables → New repository variable**, add:

| Variable name | Value |
|---|---|
| `FRONTEND_ORIGIN` | The same Netlify production HTTPS origin |
| `CAREEROS_DISCOVERY_ENABLED` | `true` |

The database credential belongs in **Secrets**, never Variables, YAML, comments or screenshots. Restrict repository write access: trusted workflow code can access this credential.

Open **Actions → CareerOS scheduled discovery → Run workflow → main → Run workflow**. This option appears after the workflow is merged into the default branch. A skipped job means the opt-in variable is missing/not `true`, or you selected a non-default branch.

After completion, inspect **CareerOS → Sources** for a finished scan, source counts and imported opportunities. A successful worker with no cloud account or no due accounts can import nothing; check the app's scan timestamp, not just the green Actions tick.

GitHub attempts to run the worker hourly at minute 17 UTC (**:47 in India**). Healthy accounts become due six hours after a completed scan; actual scans occur at a later hourly tick. **Queue a check** makes an account due but waits for the next worker; for an immediate attempt, queue it then manually run the workflow. Pausing discovery in the app remains respected.

Schedules can be delayed or dropped by GitHub. Public-repository schedules are disabled after 60 days without repository activity; re-enable the workflow from Actions if this happens. Set `CAREEROS_DISCOVERY_ENABLED=false` to stop new scheduled work. Do not treat hourly timing as guaranteed.

The workflow runs only on schedule or manual dispatch from the default branch, uses read-only repository permissions and prevents overlapping runs. Its wrapper hides raw worker output from public logs. Inspect private source health inside CareerOS for details; failures before the app connects require checking the secret, origin, database availability and API migration status. Each worker invocation has a 15-minute timeout; larger multi-user installations need a different capacity plan.

## 7. Optional providers and final verification

Ten starter public employer feeds need no search key. To expand discovery, add `BRAVE_SEARCH_API_KEY` as a GitHub Actions **secret** and as a Render environment variable. Provider usage can cost money; it is optional.

For optional email, add `RESEND_API_KEY` as an Actions secret and `EMAIL_FROM` as an Actions variable; add both on Render as environment variables. Configure a verified sender and enable email in your profile. Without these, alerts stay in the app. Never place these credentials on Netlify.

Run:

```powershell
.\.venv\Scripts\python.exe scripts/check-deployment.py --url https://YOUR_ACTUAL_NETLIFY_ADDRESS
```

Then verify login/logout, saved profile changes after reload, resume upload and one real scan in Sources. Hosted discovery can prepare drafts; it does **not** submit applications to employers. The optional browser runner remains local and separately configured.

References: [Render free limits](https://render.com/docs/free), [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [GitHub scheduled workflow limitations](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
