#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

TRADE_DATE="${ROI_SNIPS_TRADE_DATE:-$(TZ=America/New_York date +%Y-%m-%d)}"
OUT="reports/readiness/grok_research_canary_${TRADE_DATE}.json"
mkdir -p reports/readiness
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON_BIN" -m src.workflows.grok_research_readiness --trading-date "$TRADE_DATE" --output "$OUT"
