#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=true
export ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false

exec "$PYTHON_BIN" -m src.approval.command_processor FLAT ALL NOW
