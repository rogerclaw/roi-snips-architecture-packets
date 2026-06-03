#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

if [ "${1:-}" = "--loop" ]; then
  while true; do
    "$PYTHON_BIN" -m src.workflows.live_monitor
    sleep "${ROI_SNIPS_MONITOR_POLL_SECONDS:-30}"
  done
else
  "$PYTHON_BIN" -m src.workflows.live_monitor
fi
