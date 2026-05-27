#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="$ROOT/reports/live_monitor/shell_capable_shadow"
CANARY_PATH="$LOG_DIR/canary_${STAMP}.json"
VALIDATION_LOG="$LOG_DIR/validation_${STAMP}.log"
mkdir -p "$LOG_DIR"

PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

cat > "$CANARY_PATH" <<JSON
{
  "generated_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "cwd": "$ROOT",
  "shell": "${SHELL:-unknown}",
  "python": "$PYTHON",
  "validation_script_exists": $(test -f "$ROOT/scripts/run_next_open_shadow_validation.py" && echo true || echo false),
  "orders_allowed": false,
  "broker_account_inspection_allowed": false,
  "broker_orders_inspection_allowed": false,
  "broker_positions_inspection_allowed": false
}
JSON

if [[ "${1:-}" == "--canary-only" ]]; then
  echo "$CANARY_PATH"
  exit 0
fi

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=false
export ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false
export ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT=true
export ROI_SNIPS_SKIP_BROKER_STATE_FOR_SHADOW=true
export ROI_SNIPS_RUN_CONTINUATION_MONITOR=true
export ROI_SNIPS_GROK_SEARCH_TIMEOUT_SECONDS="${ROI_SNIPS_GROK_SEARCH_TIMEOUT_SECONDS:-8}"
export STOCKTWITS_TIMEOUT_SECONDS="${STOCKTWITS_TIMEOUT_SECONDS:-3}"

exec "$PYTHON" "$ROOT/scripts/run_next_open_shadow_validation.py" "$@" > "$VALIDATION_LOG" 2>&1
