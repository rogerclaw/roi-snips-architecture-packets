#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=false
export ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false

echo "[1/5] Running research pipeline"
if [ "${ROI_SNIPS_MECHANICAL_CHECKS_RUN_DEEP_MINI:-false}" = "true" ]; then
  "$PYTHON_BIN" -m src.workflows.research_pipeline
else
  SMOKE_SKIP_DEEP_MINI_NOT_FOR_LIVE_SELECTION=true ROI_SNIPS_SKIP_DEEP_MINI=true "$PYTHON_BIN" -m src.workflows.research_pipeline --skip-deep-mini
fi

echo "[2/5] Generating premarket report"
"$PYTHON_BIN" -m src.workflows.premarket_pipeline

echo "[3/5] Running live monitor"
"$PYTHON_BIN" -m src.workflows.live_monitor

echo "[4/5] Checking operator status path"
"$PYTHON_BIN" -m src.approval.command_processor STATUS

echo "[5/5] Running unit test harness (if pytest installed)"
if "$PYTHON_BIN" -m pytest -q tests; then
  true
else
  echo "pytest execution failed" >&2
  exit 1
fi

echo "Mechanical checks complete"
