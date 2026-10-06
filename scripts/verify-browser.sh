#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
qa_dir="$(mktemp -d "${TMPDIR:-/tmp}/careeros-e2e.XXXXXX")"
python_bin="${PYTHON_BIN:-.venv/bin/python}"
export FRONTEND_ORIGIN="http://localhost:${WEB_PORT:-3000}"
export API_BASE_URL="http://127.0.0.1:${API_PORT:-8000}"
export E2E_BASE_URL="$FRONTEND_ORIGIN"
# Always isolate tests from the developer's .env database.
# E2E_DATABASE_URL, if set, must be a separate disposable database.
export DATABASE_URL="${E2E_DATABASE_URL:-sqlite:///$qa_dir/e2e.db}"
export ENVIRONMENT=development COOKIE_SECURE=false REGISTRATION_ENABLED=true
export RESEND_API_KEY= AI_API_KEY= CAREEROS_E2E=1 E2E_FIXTURE_FEED=1
export DEMO_PASSWORD="${DEMO_PASSWORD:-CareerOS-local-demo-2026}"
"$python_bin" -m alembic upgrade head
"$python_bin" -m careeros.seed
"$python_bin" -m uvicorn e2e_server:app --app-dir scripts --host 127.0.0.1 --port "${API_PORT:-8000}" > "$qa_dir/api.log" 2>&1 &
api_pid=$!
(cd apps/web && exec node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port "${WEB_PORT:-3000}") > "$qa_dir/web.log" 2>&1 &
web_pid=$!
cleanup() {
  result=$?
  if [[ "$result" != "0" ]]; then
    tail -40 "$qa_dir/api.log" "$qa_dir/web.log"
  fi
  kill "$api_pid" "$web_pid" 2>/dev/null || true
  printf 'Browser verification logs: %s\n' "$qa_dir"
}
trap cleanup EXIT
"$python_bin" - <<'PY'
import os, time, urllib.request
for url in [os.environ['API_BASE_URL']+'/ready', os.environ['FRONTEND_ORIGIN']]:
    for attempt in range(80):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200: break
        except OSError: time.sleep(.25)
    else: raise SystemExit('Server did not become ready: '+url)
print('Real API, migrated database and production frontend ready; external feed uses fixtures')
PY
cd apps/web
npm run test:e2e
