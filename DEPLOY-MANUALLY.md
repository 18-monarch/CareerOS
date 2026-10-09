# CareerOS: manual deployment guide

Deploy the website on **Netlify**, the Python API and scheduled discovery on **Render**, and the database on **Neon**. This package is built and tested locally; it is not a live deployment. Use this guide from top to bottom. Advanced details are in `docs/DEPLOYMENT.md`.

## Before you begin

- Accounts: GitHub, Netlify, Render and Neon.
- On Windows: Git, Python 3.12 and Node.js 24.15+ (24.x).
- Extract this ZIP into a new folder. Work inside its `careeros` folder, which contains `render.yaml` and `netlify.toml`. Keep your old local folder and database backup.
- The configuration uses a Free Render API and **one paid cron job with a $1/month minimum**. Cron is billed by active running time; this is not a fixed total project price. Other services/providers have their own usage limits. Review the price before Apply. A custom domain is optional.
- Your existing local account/data are not automatically copied to the new cloud database.

## 1. Upload the project to GitHub

On GitHub, create an empty **private** repository named `CareerOS`. Do not add a README, license or `.gitignore`; these files and the Git history are already in the ZIP.

Open PowerShell inside the extracted `careeros` folder. Run:

```powershell
git status
git remote -v
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/CareerOS.git
git push -u origin main
```

Replace `YOUR_GITHUB_USERNAME`. If `origin` already exists, verify its URL rather than adding another. Do not run `git init` or force-push. If GitHub rejects the push because the new repository contains files, use an empty repository or integrate its history; do not discard existing work.

In GitHub's Actions tab, wait for the checks to finish. Native PostgreSQL and Windows verification run there. Do not deploy a failing commit. Never upload `.env`, `careeros.db`, `.venv`, `node_modules` or real resumes separately.

## 2. Create a dedicated Neon database

Create a project named `CareerOS`, choose PostgreSQL 17 and Singapore if offered. Use a new database for CareerOS, separate from FleetMesh or any other app.

Open the connection details and turn **connection pooling off**. Copy the complete direct connection URL. It should start with `postgresql://` or `postgresql+psycopg://`, include `sslmode=require`, and have no `-pooler` in the hostname. Copy only the URL, not the surrounding `psql` command or quotes.

Keep this URL private: it contains the database password. You will paste it into Render and the hidden local account-setup prompt, not Netlify or GitHub files.

## 3. Create the Netlify project and note its address

Import the CareerOS repository from GitHub. Use these build settings (root `netlify.toml` supplies them):

| Setting | Value |
|---|---|
| Branch | `main` |
| Base directory | `apps/web` |
| Build command | `node scripts/check-hosted-env.mjs && npm run build` |
| Publish directory | `.next` |
| Node.js | `24` |

Use the automatic Next.js adapter. Do not drag-and-drop this source ZIP as a static website.

Choose an available project name and record the **actual production address** Netlify assigns, such as `https://your-careeros.netlify.app`. If Netlify starts a build immediately, it will fail with a clear missing-configuration message until step 5. This is expected: the API URL does not exist yet. Do not change application code to bypass that check.

## 4. Deploy Render using the included Blueprint

In Render, create a new **Blueprint** and connect the same repository. Keep the repository root as the Blueprint location. Use `render.yaml`.

It should show exactly these CareerOS services:

| Service | Type | Purpose |
|---|---|---|
| `careeros-api` | Free Python web service | Account, matching and dashboard APIs |
| `careeros-discovery` | Starter cron job | Internet checks, ranking, drafts and alerts |

Supply these values when prompted:

| Variable | Value |
|---|---|
| `DATABASE_URL` | The private direct Neon URL from step 2 |
| `FRONTEND_ORIGIN` | The actual Netlify production HTTPS address, with no trailing slash |

The Blueprint already configures secure cookies, production mode, closed registration, the worker schedule and automatic migrations under a lock. Do not add a second database or the old ingestion/daily/weekly cron services. Review the charges, then Apply.

Wait for the API to become live. Copy the **actual API address** Render assigns. Open that address followed by `/ready`; it should return HTTP 200 and schema `e91a05`. If the API is sleeping, wait about a minute and retry.

## 5. Connect Netlify to Render

In Netlify's environment-variable settings, add:

| Name | Value |
|---|---|
| `API_BASE_URL` | Actual Render API HTTPS address, with no trailing slash |
| `FRONTEND_ORIGIN` | Actual Netlify production HTTPS address, with no trailing slash |

Make both values available to **builds and functions**. Use the same `FRONTEND_ORIGIN` on Netlify and Render. Do not add `NEXT_PUBLIC_` prefixes. Database/search/email credentials stay in Render.

Trigger a new production deploy on Netlify. Open the production address after it succeeds. Preview URLs intentionally cannot access account data.

## 6. Create your cloud account privately

Registration is disabled by design. Use the included interactive command; it keeps your database URL/password out of shell command history and does not change your local `.env` or database.

If the extracted folder has no Python virtual environment, prepare one in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

If you already have a working `.venv`, reuse it and run the two install commands to update dependencies/code.

Create the account:

```powershell
.\.venv\Scripts\python.exe -m careeros.cloud_account
```

At its prompts, paste the direct Neon URL (hidden), enter your email/name, and choose a password of at least 12 characters (hidden, entered twice). Pasting may look blank; press Enter once pasted. The Render database migration must already have succeeded. Existing accounts are never overwritten.

Then sign in through the Netlify production URL. Add your actual education, graduation year, skills, verified project evidence, portfolio and PDF resumes. Select both software interests and **Product Design / UI–UX** if desired.

## 7. Start useful internship checks

In Render, select `careeros-discovery` and **Trigger Run** once when it is idle. Wait for completion. In CareerOS → Sources, verify a finished check, source counts and imported opportunities.

After that, the cron runs hourly at **:45 in India**. It only performs a full scan when your account is due. Successful scans become due six hours after completion, so scheduled checks are roughly six to seven hours apart. Failed scans retry on a later hourly run. The laptop can be off.

In CareerOS, **Queue a check** requests work for the next cron run; it does not instantly launch the worker. Pause/resume is saved. Running the worker again should not duplicate unchanged opportunities or alerts.

Ten public employer feeds need no key. To expand beyond them, add `BRAVE_SEARCH_API_KEY` to the shared Render environment group. Recommended limits: `RESEARCH_QUERY_LIMIT=4` and `RESEARCH_RESULT_LIMIT=12`. A provider account and its own usage budget are required.

For email alerts, add `RESEND_API_KEY` and a verified `EMAIL_FROM` to that same group. Redeploy affected services, enable email in your profile, and verify delivery. Without email configuration, notifications remain inside CareerOS.

## 8. Verify the deployed app

From the project folder:

```powershell
.\.venv\Scripts\python.exe scripts/check-deployment.py --url https://YOUR_ACTUAL_NETLIFY_ADDRESS
```

Then verify these signed-in actions yourself:

1. Log in, edit a profile field, reload and confirm it remains saved.
2. Upload a PDF resume and view its metadata.
3. Check internship categories, original source links and eligibility explanations.
4. Confirm one real scheduled scan and one notification.
5. Prepare an application and review its packet.
6. Log out, then log in again.

The smoke command is read-only. It does not apply to employers or create jobs/accounts.

## What hosting does and does not automate

The hosted system discovers opportunities, categorizes/matches them, creates alerts and prepares enabled application drafts while your laptop is off. A high score is not confirmed eligibility; missing requirements stay uncertain.

Browser submission is **not deployed by this setup**. The optional local runner supports standard Lever forms, requires the correct cloud database/approved queue, and hands off CAPTCHA or unfamiliar questions. Do not assume an existing local SQLite runner can see cloud approvals. Start with reviewed packets and manual submission until you deliberately configure that runner.

## Troubleshooting

| Symptom | Check |
|---|---|
| Netlify build says an origin is missing | Add both variables for builds and functions, then redeploy |
| 403 on login/save | `FRONTEND_ORIGIN` must exactly match the production URL on both hosts; no trailing slash |
| Preview shows account access disabled | Open the production URL |
| API unavailable on first visit | Free API may be waking; wait about a minute, retry, then inspect Render logs |
| `/ready` is not 200 | Inspect Render startup/migration logs and the direct Neon URL |
| No internships yet | Confirm your cloud account exists, discovery is enabled, and the cron ran successfully |
| Queue button does not fetch immediately | Wait for the next cron tick or trigger an idle worker from Render |
| No email | Verify provider key, sender and profile email preference; inspect delivery errors |
| Old local password/account does not work | Cloud is a separate database; use the cloud account created in step 6 |
| Cloud account setup fails | Verify direct URL/TLS, current schema, email/password requirements and whether that email already exists |

For updates, push to `main`, wait for CI, verify successful deployments and rerun the smoke check. Back up valuable data before schema changes. Do not reset the database to fix deployment errors.

Detailed test evidence: `docs/VERIFICATION.md`. Native Windows/PostgreSQL CI and actual hosted end-to-end verification must be checked on your deployment; local passing tests do not prove that the cloud accounts, environment variables and providers are configured correctly.
