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
export ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH:-false}"
export ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH:-true}"
export ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS="${ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS:-1800}"
export ROI_SNIPS_DEEP_MINI_POLL_SECONDS="${ROI_SNIPS_DEEP_MINI_POLL_SECONDS:-15}"
export ROI_SNIPS_GROK_SEARCH_TIMEOUT_SECONDS="${ROI_SNIPS_GROK_SEARCH_TIMEOUT_SECONDS:-8}"
export STOCKTWITS_TIMEOUT_SECONDS="${STOCKTWITS_TIMEOUT_SECONDS:-3}"

set +e
"$PYTHON_BIN" -m src.workflows.live_readiness --probe-symbol "${ROI_SNIPS_READINESS_PROBE_SYMBOL:-SPY}" \
  > "$LOG_DIR/live_readiness_latest.json"
LIVE_READINESS_RC=$?
set -e
printf '{"status":"recorded","step":"live_readiness","exit_code":%s,"note":"premarket_research_continues;final_arming_gate_enforces_go_no_go"}\n' "$LIVE_READINESS_RC" \
  > "$LOG_DIR/live_readiness_latest.status.json"
scripts/check_grok_research_readiness.sh \
  > "$LOG_DIR/grok_research_canary_latest.json"
set +e
"$PYTHON_BIN" -m src.workflows.grok_research_pipeline \
  > "$LOG_DIR/grok_heat_latest.json"
GROK_RESEARCH_RC=$?
set -e
printf '{"status":"recorded","step":"grok_research_pipeline","exit_code":%s,"note":"grok_research_only_feeds_deep_mini;final_arming_gate_enforces_deep_mini_ticket"}\n' "$GROK_RESEARCH_RC" \
  > "$LOG_DIR/grok_heat_latest.status.json"
set +e
"$PYTHON_BIN" -m src.workflows.research_pipeline \
  > "$LOG_DIR/research_latest.json"
DEEP_RESEARCH_RC=$?
set -e
printf '{"status":"recorded","step":"governed_deep_research_pipeline","exit_code":%s,"note":"deep_mini_primary_live_selector;final_arming_gate_enforces_deep_mini_ticket"}\n' "$DEEP_RESEARCH_RC" \
  > "$LOG_DIR/research_latest.status.json"
"$PYTHON_BIN" -m src.workflows.premarket_pipeline \
  > "$LOG_DIR/premarket_latest.json"

echo "{\"status\":\"ok\",\"mode\":\"live_trade_ready_premarket\",\"generated_at_utc\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
