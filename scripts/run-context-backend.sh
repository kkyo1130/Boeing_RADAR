#!/bin/sh
# Opt-in contextual STT diagnostic; output requires review, never auto-adopts a target.
set -eu
cd "$(dirname "$0")/.."
export RADAR_STT_CALLSIGN_CONTEXT=1
exec sh scripts/run-hybrid-backend.sh
