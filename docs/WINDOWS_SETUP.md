# CareerOS on Windows PowerShell

Use Python 3.12 and Node.js **24.15.0 or newer within 24.x**. Node 24.8.0 is too old for the locked frontend test dependencies. After updating Node, close and reopen PowerShell and VS Code so they use the new executable. Check `node --version`; `where.exe node` helps find an older installation still on PATH.

## Recovering the original ZIP installation

The October 8 fix corrects two Windows portability defects: Unix-only `uvloop` was pinned without a platform marker, and local SQLite job locks imported Unix-only `fcntl`. Both are fixed in this package. A Python package reporting “Successfully installed careeros” after `--no-deps` does not mean its dependencies installed successfully.

Download the updated ZIP. Keep your existing folder as a backup. Copy the updated project files into your working folder, replacing source/configuration files. Preserve your `.env`, `apps/web/.env.local`, `.venv` and `careeros.db` if present; none of those are included in the ZIP. Do not copy or replace the `.git` folder if you have made your own commits.

Open a fresh PowerShell in the working `careeros` folder. Your earlier virtual environment can be reused. For a first installation only, create it with `py -3.12 -m venv .venv`.

Run each command separately; continue only after it succeeds:

```powershell
.\.venv\Scripts\python.exe -m pip install --timeout 120 --retries 5 -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --timeout 120 --retries 5 --no-deps -e .
.\.venv\Scripts\python.exe -m pip check
```

Seeing `Ignoring uvloop: markers ... don't match your environment` on Windows is expected. Existing downloads may be reused from pip's cache.

## Local settings and database

If the settings files do not yet exist, create them without overwriting existing settings:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path apps/web/.env.local)) { Copy-Item apps/web/.env.example apps/web/.env.local }
notepad .env
```

For local SQLite, set this line in `.env`, save and close Notepad:

```dotenv
DATABASE_URL=sqlite:///./careeros.db
```

Then create/update the schema:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## Frontend dependencies

From the project root:

```powershell
cd apps/web
npm.cmd ci --fetch-retries=5 --fetch-timeout=120000
cd ../..
```

`npm.cmd` avoids PowerShell selecting `npm.ps1` when script execution is restricted; no execution-policy change is needed. `npm ci` recreates dependencies using the committed lockfile. Do not delete or regenerate `package-lock.json` to fix a network interruption.

If `ECONNRESET` or a download timeout persists, retry on a stable connection. If `EPERM` prevents npm cleanup, stop CareerOS dev servers with Ctrl+C and close editor tasks using that folder, then retry. If the directory remains locked, restart Windows and rerun the command before opening the editor. Do not disable TLS verification or change unrelated proxy/security settings.

## Start and use

Terminal 1, project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn careeros.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2, project root:

```powershell
cd apps/web
npm.cmd run dev
```

Open http://localhost:3000. Register your account and complete My profile. Automatic discovery connects the starter sources and checks for real technical internships within about 30 seconds; results appear in Opportunities. Check progress in Sources. Keep both terminals open. Ctrl+C stops each server; restart later with these same two commands. Keep the frontend on port 3000 because the local origin settings expect that port.

Optional demo account, in a third terminal at the project root (choose your own password):

```powershell
$env:DEMO_PASSWORD = 'Choose-your-own-long-password'
.\.venv\Scripts\python.exe -m careeros.seed --email mohit@example.com
```

The demo contains fictional jobs. There is no default login password.

Optional manual worker command (Sources → Check now is normally enough):

```powershell
.\.venv\Scripts\python.exe -m worker discover-jobs
```

The API now checks sources automatically every six hours while it runs. Pause/resume from Sources. Notifications work in-app without email credentials. Stop servers/workers before backing up `careeros.db`.

## Verification boundary

The fix was installed and tested on Linux with Windows dependency markers checked explicitly. A Windows CI job now covers actual installation, database operations, process locks and frontend build, but has not run remotely. Native Windows runtime verification still requires running it on Windows.
