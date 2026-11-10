#!/bin/sh
# Human controller + pilot demo. Models/config are prepared locally, never downloaded here.
set -eu
cd "$(dirname "$0")/.."
export RADAR_PORT="${RADAR_PORT:-8018}"
RADAR_DEMO_WEB_PORT="${RADAR_FRONTEND_PORT:-5178}"
RADAR_DEMO_PYTHON="${RADAR_PYTHON:-$PWD/.venv/bin/python}"
# Refuse occupied ports rather than accidentally proxying an older server.
"$RADAR_DEMO_PYTHON" - "$RADAR_PORT" "$RADAR_DEMO_WEB_PORT" <<'PYPORT'
import socket,sys
for port in sys.argv[1:]:
    with socket.socket() as sock:
        try: sock.bind(('127.0.0.1',int(port)))
        except OSError as error: sys.exit(f'Local demo port {port} unavailable: {error}')
PYPORT
export RADAR_API_TARGET="http://127.0.0.1:$RADAR_PORT"
export RADAR_DATABASE_URL="${RADAR_DATABASE_URL:-sqlite:///$PWD/.demo/live-demo.db}"
# Opt-in context retains its review gate; this launcher does not enable it.
sh scripts/run-hybrid-backend.sh &
RADAR_DEMO_API_PID=$!
trap 'kill "$RADAR_DEMO_API_PID" 2>/dev/null || true' EXIT INT TERM
RADAR_DEMO_READY=0
for RADAR_DEMO_TRY in 1 2 3 4 5 6 7 8 9 10; do
  kill -0 "$RADAR_DEMO_API_PID" 2>/dev/null || { wait "$RADAR_DEMO_API_PID"; exit 1; }
  if curl --silent --fail "$RADAR_API_TARGET/api/demo/status" >/dev/null; then RADAR_DEMO_READY=1; break; fi
  sleep 1
done
[ "$RADAR_DEMO_READY" = 1 ] || { echo 'Backend did not become ready.' >&2; exit 1; }
cd frontend
npm run dev -- --host 127.0.0.1 --port "${RADAR_FRONTEND_PORT:-5178}"
