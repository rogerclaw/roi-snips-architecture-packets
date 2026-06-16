#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

PROBE_SYMBOL="${ROI_SNIPS_READINESS_PROBE_SYMBOL:-SPY}"
BROKER_PROVIDER="${ROI_SNIPS_READINESS_BROKER_PROVIDER:-}"
MARKET_DATA_PROVIDER="${ROI_SNIPS_READINESS_MARKET_DATA_PROVIDER:-}"

ARGS=( -m src.workflows.live_readiness --probe-symbol "$PROBE_SYMBOL" )
if [ -n "$BROKER_PROVIDER" ]; then
  ARGS+=( --broker-provider "$BROKER_PROVIDER" )
fi
if [ -n "$MARKET_DATA_PROVIDER" ]; then
  ARGS+=( --market-data-provider "$MARKET_DATA_PROVIDER" )
fi

exec "$PYTHON_BIN" "${ARGS[@]}"
