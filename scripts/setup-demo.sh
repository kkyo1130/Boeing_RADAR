#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements-demo.txt -e './vision[capture]'
mkdir -p .demo/audio .demo/bin
xcrun swiftc vision/native/ocr.swift -o .demo/bin/radar-ocr
.venv/bin/python scripts/prepare-demo.py
cd frontend
npm ci
