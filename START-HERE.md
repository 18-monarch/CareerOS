# CareerOS — start here

**Deploy online:** open [DEPLOY-MANUALLY.md](DEPLOY-MANUALLY.md) for the complete Netlify + Render + Neon walkthrough.

This October 9 update adds category-based internship research, product design, real PDF attachments, an application desk, a local Lever browser runner, and safer upgrades. Your existing career tracker, learning tools and accounts are retained.

For cloud hosting on **Netlify + Render + Neon**, follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). The cloud configuration is prepared; creating the Git repository and deploying the services are still pending.

## Update your existing Windows installation

1. Stop both CareerOS terminals and any application runner. Back up your existing `careeros` folder.
2. Copy the new project files into your existing folder. **Keep your `.env`, `apps/web/.env.local`, `.venv`, `careeros.db`, and existing `.git` history.** The release contains no personal database or credentials.
3. Double-click `RUN-WINDOWS.cmd`. It installs the locked dependencies, builds the frontend, and opens the two server terminals. Requirements: Python 3.12 and Node.js 24.15+ in the 24.x series. Internet access is needed for the first installation and job checks.
4. Open http://localhost:3000 once both terminals are ready. Sign in with your existing account. The local SQLite database is backed up and migrated automatically before discovery starts. The backup is beside the database, named `careeros.db.backup-...`.

You can still use the previous two terminal commands. The automatic migration is inside the backend startup, not just the launcher. PostgreSQL and production migrations remain an explicit `python -m alembic upgrade head` operation. Check http://localhost:8000/ready — the current schema is `e91a05`.

If you have an older Python virtual environment, the launcher reinstalls dependencies in it; it does not delete your account or database. If setup reports an error, keep the terminal output. Do not delete the database to troubleshoot.

## Make recommendations useful for you

In **My profile**, enter your actual graduation year, education, skills and work authorizations. Select career interests, including **Product Design / UI–UX**. A technology mentioned in one of your projects is not automatically verified evidence. Add your actual portfolio URL for design applications.

Open **Internship brief**. Opportunities are grouped into software/SDE, backend, frontend, full-stack, AI/ML/data, cloud/platform, cybersecurity, QA, product design, UX research and design engineering. Cards show fit, eligibility uncertainty, relevant project evidence, next action, original link, posting date (when provided), first discovery date and last check. One canonical opportunity may appear in multiple relevant categories.

**Sources** shows the live checker and pause/resume controls. The first scan normally starts within 30 seconds and may take several minutes; successful checks repeat every six hours while the backend is running. Ten public employer boards require no API key. Confirmed source disappearance closes research-imported postings; transient network failures do not.

## Broader internet research

For searches beyond connected feeds, create your own Brave Search API account/key and set this in the root `.env`:

```dotenv
BRAVE_SEARCH_API_KEY=your-own-key
RESEARCH_QUERY_LIMIT=4
RESEARCH_RESULT_LIMIT=12
```

Restart the backend and use Sources → Check now. The key is server-only. The provider may charge under your plan; this release does not include credits or a shared key. Queries contain role/category and preferred country, not your email, resume or personal answers. Search categories and countries rotate over successive cycles. At four queries every six hours, one continuously running user can generate approximately 16 searches a day, plus manual checks.

The **research inbox** retains search results and deduplicates links. Recognized Greenhouse, Lever and Ashby posting URLs are checked against their public APIs and imported if relevant. Other results remain explicitly **Review required** with their original links; snippets never establish eligibility. Use **Inspect an internship link** for a URL you already found. An HTTP error is not proof a role has closed. No API key means the ten feeds and direct link inspection still work, but broad web search stays off.

## Prepare and apply

1. In **My profile → Resume versions**, add software and/or design resume metadata, then upload a PDF up to 650 KB. PDFs stay in your CareerOS database until an authorized application sends one to an employer.
2. In **Application desk → Application preferences & automation**, select the appropriate resume for each track, phone, countries and limits. Saved answers map an exact form question to your truthful response.
3. Choose **Prepare application** on a brief or opportunity. Or enable automatic draft preparation. Drafts use your stored facts and skill/project evidence; they do not invent experience. A design application requires a portfolio.
4. Review the candidate details, resume, cover letter, answers, original requirements and internship availability. Save edits, check the authorization box, then approve the application. Approval alone does **not** mean it has been submitted.
5. Double-click `START-APPLICATION-RUNNER.cmd`. It installs Playwright Chromium, asks for your CareerOS email, and asks you to type **SUBMIT** to process approved applications continuously. Enter without SUBMIT runs a form-fill preview check without submission.

The CLI equivalent from the project root is:

```powershell
.\.venv\Scripts\python.exe -m careeros.apply_runner --email YOUR_EMAIL --submit --watch
```

The runner currently supports **standard forms on jobs.lever.co**. It checks the live posting again, fills known fields, uploads the exact approved PDF and checks required fields. CAPTCHA, unfamiliar required widgets/questions, agreements and unsupported sites produce **Handoff**. You can download the prepared packet and finish manually. It never bypasses a challenge or takes an assessment.

Only employer-page confirmation marks an application **Submitted** and updates the Applications tracker. An ambiguous click/timeout/crash becomes **Uncertain**, with no automatic retry. Check the employer site/email; use the manual Applications tracker to record a verified outcome. Submitted/uncertain drafts cannot be silently regenerated. Changed profile, settings, resume or posting facts invalidate approval. Approvals expire after 24 hours.

**Automatic approval mode:** optional and off by default. Requires auto-prepare, an exact company allowlist, country/score limits, an eligible posting that you have reviewed in the opportunity editor, an uploaded resume, and a design portfolio when relevant. Complete availability and other form answers yourself. Both discovery and the local application runner must be running. An empty company allowlist allows no automatic approvals. The daily limit counts submission attempts, including uncertain attempts.

## Honest limits and verification

This is a tested local release, not a promise of error-free operation on every employer website. No real employer application was submitted during testing. The live feed scan checked 226 postings across ten boards and retained seven internships, including one Product Design Intern in India. Current openings can change.

85 backend tests, five frontend component tests, seven Chromium browser scenarios, lint/type checks and the production build passed for this release (see `docs/VERIFICATION.md`). The search-provider transport was exercised with controlled responses; no credentialed Brave search was made. Submission was tested against a controlled employer-form fixture, not a production employer. Native Windows execution, current native PostgreSQL deployment and cloud hosting were not performed here.

Your laptop must stay awake and connected for local automation. Email alerts require separate Resend configuration; without it, notifications are in-app. Market and visa notes remain sourced manual entries. Matching scores are explanations of fit, not interview or hiring probabilities.
