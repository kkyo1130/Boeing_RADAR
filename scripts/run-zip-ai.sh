#!/bin/sh
# Models stay in the unpacked bundle; application code and flight DB stay here.
set -eu
cd "$(dirname "$0")/.."
PROJECT_ROOT="$PWD"
BUNDLE_ROOT="${1:-$HOME/Downloads/RADAR-Mac-740df89}"
BUNDLE_ROOT="$(cd "$BUNDLE_ROOT" && pwd)"
PY="${RADAR_AI_PYTHON:-$BUNDLE_ROOT/.venv/bin/python}"
if [ -z "${RADAR_CHARACTER_CHECKPOINT:-}" ] && [ -f "$PROJECT_ROOT/.demo/active-vision.json" ]; then
  export RADAR_CHARACTER_CHECKPOINT="$("$PY" -c 'import json,sys; from pathlib import Path; root=Path(sys.argv[1]); d=json.loads((root/".demo/active-vision.json").read_text()); p=d.get("checkpoint"); print((root/p).resolve() if p else "")' "$PROJECT_ROOT")"
  export RADAR_CHARACTER_SHA256="$("$PY" -c 'import json,sys; from pathlib import Path; print(json.loads((Path(sys.argv[1])/".demo/active-vision.json").read_text()).get("sha256",""))' "$PROJECT_ROOT")"
fi
API_PORT="${RADAR_AI_API_PORT:-8019}"
WEB_PORT="${RADAR_AI_WEB_PORT:-5179}"
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/vision/src"
VISION_ROOT="${RADAR_VISION_ROOT:-$HOME/Desktop/Boeing_RADAR-vision}"
export RADAR_VISION_CHECKPOINTS="$VISION_ROOT/vision/checkpoints/mcp_ocr_v3"
export RADAR_VISION_TARGET="http://127.0.0.1:8766"
export RADAR_DEMO_ENABLED=1 RADAR_NER_BACKEND=bert-hybrid
export RADAR_NER_MODEL="$BUNDLE_ROOT/assets/bert-hybrid-model"
export RADAR_WHISPER_MODEL="$BUNDLE_ROOT/assets/model"
export RADAR_V2_CONFIG="$BUNDLE_ROOT/assets/config.json"
export RADAR_DEMO_AUDIO="$BUNDLE_ROOT/assets/audio"
export RADAR_DATABASE_URL="sqlite:///$PROJECT_ROOT/.demo/zip-ai.db"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4
export RADAR_REGION_OCR_BINARY="$PROJECT_ROOT/.demo/bin/region-ocr"
export RADAR_OCR_BINARY="$PROJECT_ROOT/.demo/bin/zip-radar-ocr"
export RADAR_API_TARGET="http://127.0.0.1:$API_PORT"
"$PY" -c 'import cv2, faster_whisper, transformers, torch, reportlab, pypdf; from pathlib import Path; import os; assert Path(os.environ["RADAR_NER_MODEL"], "model.safetensors").is_file(); assert Path(os.environ["RADAR_WHISPER_MODEL"], "model.bin").is_file()'
mkdir -p .demo/bin
if [ ! -x "$RADAR_OCR_BINARY" ] || [ vision/native/ocr.swift -nt "$RADAR_OCR_BINARY" ]; then
  swiftc vision/native/ocr.swift -o "$RADAR_OCR_BINARY"
fi
if [ ! -x "$RADAR_REGION_OCR_BINARY" ] || [ vision/native/regions.swift -nt "$RADAR_REGION_OCR_BINARY" ]; then
  swiftc vision/native/regions.swift -o "$RADAR_REGION_OCR_BINARY"
fi
"$PY" - "$API_PORT" "$WEB_PORT" <<'PY'
import socket, sys
for port in [*sys.argv[1:], "8766"]:
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', int(port)))
PY
"$PY" -c 'from pathlib import Path; import os; p=Path(os.environ["RADAR_VISION_CHECKPOINTS"]); assert all((p/(k+"_best.pt")).is_file() for k in ("hdg","alt")), "Missing Vision checkpoints"'
(cd backend && exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT") &
API_PID=$!
"$PY" -m uvicorn vision.ocr_web:app --host 127.0.0.1 --port 8766 &
VISION_PID=$!
trap 'kill "$API_PID" "$VISION_PID" 2>/dev/null || true' EXIT INT TERM
printf 'Operations: http://127.0.0.1:%s/operations\nSeparate local DB; start a new flight. Vision lab: /cockpit (automatic ROI); demo device panel uses manual ROI.\n' "$WEB_PORT"
export PATH="/opt/homebrew/opt/node@24/bin:$PATH"
cd frontend
npm run dev -- --host 127.0.0.1 --port "$WEB_PORT" --strictPort
