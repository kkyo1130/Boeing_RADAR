#!/bin/bash
# Local image-only YOLO MCP detector + CharacterCNN. Models/captures stay local.
set -eu
RADAR_LOCAL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RADAR_LOCAL_ROOT"
export PYTHONPATH="$RADAR_LOCAL_ROOT:$RADAR_LOCAL_ROOT/vision/src${PYTHONPATH:+:$PYTHONPATH}"
export RADAR_DEMO_ENABLED=1
export RADAR_V2_CONFIG="${RADAR_V2_CONFIG:-$RADAR_LOCAL_ROOT/.demo/config.json}"
export RADAR_DATABASE_URL="${RADAR_DATABASE_URL:-sqlite:///$RADAR_LOCAL_ROOT/.demo/zip-ai.db}"
export RADAR_WHISPER_MODEL="${RADAR_WHISPER_MODEL:-$RADAR_LOCAL_ROOT/.demo/model}"
export RADAR_DEMO_AUDIO="${RADAR_DEMO_AUDIO:-$RADAR_LOCAL_ROOT/.demo/audio}"
export RADAR_API_TARGET=http://127.0.0.1:8019
export RADAR_VISION_TARGET=http://127.0.0.1:8766
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4
unset RADAR_OCR_BINARY RADAR_REGION_OCR_BINARY RADAR_VISION_CHECKPOINTS
case "${1:-all}" in
  api) cd backend; exec ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8019 ;;
  vision) exec .venv/bin/python -m uvicorn vision.ocr_web:app --host 127.0.0.1 --port 8766 ;;
  frontend) cd frontend; exec npm run dev -- --host 127.0.0.1 --port 5179 --strictPort ;;
  all)
    "$0" api & RADAR_LOCAL_API_PID=$!
    "$0" vision & RADAR_LOCAL_VISION_PID=$!
    trap 'kill "$RADAR_LOCAL_API_PID" "$RADAR_LOCAL_VISION_PID" 2>/dev/null || true' EXIT INT TERM
    "$0" frontend ;;
  *) echo 'Usage: scripts/run-yolo-cnn.sh [all|api|vision|frontend]' >&2; exit 2 ;;
esac
