#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
DEMO_ROOT="$PWD"
export RADAR_DEMO_ENABLED=1
export RADAR_V2_CONFIG="$DEMO_ROOT/.demo/config.json"
export RADAR_DATABASE_URL="sqlite:///$DEMO_ROOT/.demo/radar.db"
export RADAR_WHISPER_MODEL="$DEMO_ROOT/.demo/model"
export RADAR_OCR_BINARY="$DEMO_ROOT/.demo/bin/radar-ocr"
export RADAR_DEMO_AUDIO="$DEMO_ROOT/.demo/audio"
export RADAR_API_TARGET=http://127.0.0.1:8001
(cd backend && "$DEMO_ROOT/.venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8001) &
DEMO_API_PID=$!
trap 'kill "$DEMO_API_PID" 2>/dev/null || true' EXIT INT TERM
cd frontend
npm run dev -- --host 127.0.0.1 --port 5175
