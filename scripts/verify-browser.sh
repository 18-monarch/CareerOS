#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p /tmp/careeros-qa
export FRONTEND_ORIGIN="http://localhost:${WEB_PORT:-3000}"
export API_BASE_URL="http://127.0.0.1:${API_PORT:-8000}"
export E2E_BASE_URL="$FRONTEND_ORIGIN"
.venv/bin/uvicorn careeros.main:app --host 127.0.0.1 --port "${API_PORT:-8000}" > /tmp/careeros-qa/api.log 2>&1 &
api_pid=$!
(cd apps/web && npm run start -- --port "${WEB_PORT:-3000}") > /tmp/careeros-qa/web.log 2>&1 &
web_pid=$!
trap 'kill "$api_pid" "$web_pid" 2>/dev/null || true' EXIT
.venv/bin/python - <<'PY'
import time, urllib.request, os
for url in [os.environ['API_BASE_URL']+'/ready',os.environ['FRONTEND_ORIGIN']]:
    for attempt in range(40):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status==200:break
        except OSError:time.sleep(.25)
    else:raise SystemExit('Server did not become ready: '+url)
print('API and production frontend ready')
PY
cd apps/web
if [[ -n "${CHROMIUM_EXECUTABLE_PATH:-}" ]]; then
  export AGENT_BROWSER_EXECUTABLE_PATH="$CHROMIUM_EXECUTABLE_PATH"
  export AGENT_BROWSER_ARGS='--no-sandbox,--disable-dev-shm-usage,--disable-gpu'
fi
if [[ "${SKIP_AGENT_BROWSER:-0}" != "1" ]] && npx agent-browser --debug --session careeros-qa open "$FRONTEND_ORIGIN"; then
  npx agent-browser --session careeros-qa wait --load networkidle
  npx agent-browser --session careeros-qa snapshot -i
  npx agent-browser --session careeros-qa screenshot /tmp/careeros-qa/login.png
  npx agent-browser --session careeros-qa eval 'document.querySelector("[data-nextjs-dialog]") ? "ERROR_OVERLAY" : document.body.innerText.trim().length ? "HAS_CONTENT" : "BLANK"'
  npx agent-browser --session careeros-qa close
else
  printf '%s\n' 'agent-browser unavailable in this runtime; using Playwright for browser verification.'
fi
npm run test:e2e
