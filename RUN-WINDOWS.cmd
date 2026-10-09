@echo off
setlocal
cd /d "%~dp0"
echo CareerOS - local setup and start
where node >nul 2>nul
if errorlevel 1 (
  echo Install Node.js 24 LTS, then run this file again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto failed
)
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo DATABASE_URL=sqlite:///./careeros.db>> .env
)
if not exist "apps\web\.env.local" copy "apps\web\.env.example" "apps\web\.env.local" >nul
.venv\Scripts\python.exe -m pip install -r requirements.lock
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install --no-deps -e .
if errorlevel 1 goto failed
pushd apps\web
call npm ci
if errorlevel 1 goto webfailed
call npm run build
if errorlevel 1 goto webfailed
popd
start "CareerOS API - keep open" cmd /k ".venv\Scripts\python.exe -m uvicorn careeros.main:app --host 127.0.0.1 --port 8000"
start "CareerOS Web - keep open" cmd /k "cd apps\web && npm run start"
echo Open http://localhost:3000 after both terminals report ready.
echo Local SQLite upgrades automatically after making a backup.
echo See START-HERE.md for research and application setup.
pause
exit /b 0
:webfailed
popd
:failed
echo Setup failed. Read the error above; your existing database has not been deleted.
pause
exit /b 1
