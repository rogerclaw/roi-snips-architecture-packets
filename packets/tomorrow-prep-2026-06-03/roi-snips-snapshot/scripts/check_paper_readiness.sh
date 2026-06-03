#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

export ROI_SNIPS_CONFIG_PATH="${ROI_SNIPS_CONFIG_PATH:-$ROOT_DIR/configs/paper.yaml}"
export ALPACA_PAPER=true
export ALPACA_BASE_URL="${ALPACA_BASE_URL:-https://paper-api.alpaca.markets}"
export ALPACA_MARKET_DATA_FEED="${ALPACA_MARKET_DATA_FEED:-iex}"
export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION="${ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION:-false}"
export ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION="${ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION:-false}"

exec "$PYTHON_BIN" -m src.workflows.live_readiness --probe-symbol "${ROI_SNIPS_READINESS_PROBE_SYMBOL:-SPY}" "$@"
