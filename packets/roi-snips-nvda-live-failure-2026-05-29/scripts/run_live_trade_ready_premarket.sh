#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

LOG_DIR="$ROOT_DIR/reports/live_monitor/live_trade_ready"
LOCK_DIR="$ROOT_DIR/state/live_trade_ready_premarket.lock"
mkdir -p "$LOG_DIR" "$ROOT_DIR/state"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "{\"status\":\"skipped\",\"reason\":\"premarket_lock_active\",\"generated_at_utc\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=true
export ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false
export ROI_SNIPS_SKIP_DEEP_MINI="${ROI_SNIPS_SKIP_DEEP_MINI:-false}"
export ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH:-true}"
export ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS="${ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS:-1800}"
export ROI_SNIPS_DEEP_MINI_POLL_SECONDS="${ROI_SNIPS_DEEP_MINI_POLL_SECONDS:-15}"
export ROI_SNIPS_GROK_SEARCH_TIMEOUT_SECONDS="${ROI_SNIPS_GROK_SEARCH_TIMEOUT_SECONDS:-8}"
export STOCKTWITS_TIMEOUT_SECONDS="${STOCKTWITS_TIMEOUT_SECONDS:-3}"

"$PYTHON_BIN" -m src.workflows.live_readiness --probe-symbol "${ROI_SNIPS_READINESS_PROBE_SYMBOL:-SPY}" \
  > "$LOG_DIR/live_readiness_latest.json"
RESEARCH_ARGS=(-m src.workflows.research_pipeline)
if [ "${ROI_SNIPS_SKIP_DEEP_MINI}" = "true" ]; then
  RESEARCH_ARGS+=(--skip-deep-mini)
fi
"$PYTHON_BIN" "${RESEARCH_ARGS[@]}" \
  > "$LOG_DIR/research_latest.json"
"$PYTHON_BIN" -m src.workflows.premarket_pipeline \
  > "$LOG_DIR/premarket_latest.json"

echo "{\"status\":\"ok\",\"mode\":\"live_trade_ready_premarket\",\"generated_at_utc\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
