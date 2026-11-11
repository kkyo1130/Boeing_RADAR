#!/bin/sh
# Start loopback servers; CTRL+C stops only processes launched here.
set -eu
cd "$(dirname "$0")/.."
RADAR_PYTHON="${RADAR_PYTHON:-python}"
"$RADAR_PYTHON" -c 'import torch, cv2, fastapi, uvicorn'
[ -f frontend/node_modules/vite/bin/vite.js ] || { echo 'Run npm install in frontend first.' >&2; exit 1; }
"$RADAR_PYTHON" -c 'from pathlib import Path; import socket
for name in ("hdg", "alt"):
 assert Path("vision/checkpoints/mcp_ocr_v3/"+name+"_best.pt").is_file(), "Missing v3 checkpoint"
for port in (8000,8765,5173):
 with socket.socket() as sock: sock.bind(("127.0.0.1",port))'
(cd backend && exec "$RADAR_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
backend_pid=$!
"$RADAR_PYTHON" -m uvicorn vision.ocr_web:app --host 127.0.0.1 --port 8765 &
ocr_pid=$!
(cd frontend && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort) &
frontend_pid=$!
trap 'kill "$backend_pid" "$ocr_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM
printf '%s\n' 'Cockpit: http://127.0.0.1:5173/cockpit' 'Backend: http://127.0.0.1:8000/docs' 'OCR: http://127.0.0.1:8765/docs'
wait
