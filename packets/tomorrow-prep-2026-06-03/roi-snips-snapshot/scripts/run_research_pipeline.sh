#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
if [ "${ROI_SNIPS_GROK_HEAT_ONLY:-false}" = "true" ]; then
  "$PYTHON_BIN" -m src.workflows.grok_research_pipeline "$@"
else
  "$PYTHON_BIN" -m src.workflows.research_pipeline "$@"
fi
