#!/bin/sh
# Local-only BERT+rules STT backend; prepare .demo assets first (see docs).
set -eu
cd "$(dirname "$0")/.."
RADAR_RUN_ROOT="$PWD"
export RADAR_DEMO_ENABLED=1
export RADAR_NER_BACKEND=bert-hybrid
export RADAR_NER_MODEL="${RADAR_NER_MODEL:-$RADAR_RUN_ROOT/.demo/bert-hybrid-model}"
export RADAR_WHISPER_MODEL="${RADAR_WHISPER_MODEL:-$RADAR_RUN_ROOT/.demo/model}"
export RADAR_V2_CONFIG="${RADAR_V2_CONFIG:-$RADAR_RUN_ROOT/.demo/config.json}"
export RADAR_DATABASE_URL="${RADAR_DATABASE_URL:-sqlite:///$RADAR_RUN_ROOT/.demo/hybrid.db}"
export RADAR_DEMO_AUDIO="${RADAR_DEMO_AUDIO:-$RADAR_RUN_ROOT/.demo/audio}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
RADAR_RUN_PYTHON="${RADAR_PYTHON:-$RADAR_RUN_ROOT/.venv/bin/python}"
[ -f "$RADAR_NER_MODEL/radar_hybrid.json" ] || { echo 'Prepare the local BERT artifact first.' >&2; exit 1; }
[ -f "$RADAR_WHISPER_MODEL/model.bin" ] || { echo 'Configure a local faster-whisper model.' >&2; exit 1; }
[ -f "$RADAR_V2_CONFIG" ] || { echo 'Configure the callsign registry and structure policy.' >&2; exit 1; }
cd backend
exec "$RADAR_RUN_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "${RADAR_PORT:-8013}"
