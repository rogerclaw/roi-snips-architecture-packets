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
export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=false
export ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false
export ROI_SNIPS_SKIP_DEEP_MINI="${ROI_SNIPS_SKIP_DEEP_MINI:-false}"
export ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH:-false}"
export ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH:-true}"
export ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS="${ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS:-1800}"
export ROI_SNIPS_DEEP_MINI_POLL_SECONDS="${ROI_SNIPS_DEEP_MINI_POLL_SECONDS:-15}"
export ROI_SNIPS_GROK_SEARCH_TIMEOUT_SECONDS="${ROI_SNIPS_GROK_SEARCH_TIMEOUT_SECONDS:-8}"
export STOCKTWITS_TIMEOUT_SECONDS="${STOCKTWITS_TIMEOUT_SECONDS:-3}"

TRADE_DATE="${ROI_SNIPS_TRADE_DATE:-$(TZ=America/New_York date +%Y-%m-%d)}"
TRACE_FILE="$LOG_DIR/premarket_wrapper_trace_${TRADE_DATE}.jsonl"
START_FILE="$LOG_DIR/premarket_wrapper_start_${TRADE_DATE}.json"
FINAL_FILE="$LOG_DIR/premarket_wrapper_final_${TRADE_DATE}.json"

env_bool() {
  case "${1:-false}" in
    1|true|TRUE|yes|YES|on|ON) printf 'true' ;;
    *) printf 'false' ;;
  esac
}

append_trace() {
  local event="$1"
  local status="${2:-recorded}"
  local exit_code="${3:-0}"
  printf '{"event":"%s","status":"%s","exit_code":%s,"trade_date":"%s","generated_at_utc":"%s"}\n' \
    "$event" "$status" "$exit_code" "$TRADE_DATE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$TRACE_FILE"
}

write_step_status() {
  local path="$1"
  local status="$2"
  local step="$3"
  local exit_code="$4"
  local note="$5"
  local deep_mini_reached="${6:-false}"
  printf '{"status":"%s","step":"%s","exit_code":%s,"trade_date":"%s","generated_at_utc":"%s","deep_mini_required":%s,"deep_mini_reached":%s,"note":"%s"}\n' \
    "$status" "$step" "$exit_code" "$TRADE_DATE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$(env_bool "$ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH")" "$(env_bool "$deep_mini_reached")" "$note" > "$path"
}

write_final_status() {
  local status="$1"
  local exit_code="$2"
  local optional_grok_nonfatal="$3"
  local deep_mini_reached="$4"
  local blocker="$5"
  "$PYTHON_BIN" - "$FINAL_FILE" "$status" "$exit_code" "$TRADE_DATE" "$optional_grok_nonfatal" "$deep_mini_reached" "$blocker" <<'PY'
import json
import sys
from datetime import datetime, timezone
path, status, exit_code, trade_date, optional_grok_nonfatal, deep_mini_reached, blocker = sys.argv[1:8]
payload = {
    "status": status,
    "mode": "live_trade_ready_premarket",
    "trade_date": trade_date,
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "exit_code": int(exit_code),
    "grok_required": False,
    "deep_mini_required": True,
    "optional_grok_failure_nonfatal": optional_grok_nonfatal.lower() == "true",
    "deep_mini_reached": deep_mini_reached.lower() == "true",
    "orders_previewed": False,
    "orders_submitted": False,
    "blockers": [] if not blocker else [blocker],
}
open(path, "w", encoding="utf-8").write(json.dumps(payload, indent=2, sort_keys=True))
PY
}

printf '{"status":"started","event":"premarket_wrapper_start","trade_date":"%s","generated_at_utc":"%s","grok_required":%s,"deep_mini_required":%s,"orders_allowed":false}\n' \
  "$TRADE_DATE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "$(env_bool "$ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH")" "$(env_bool "$ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH")" > "$START_FILE"
cp "$START_FILE" "$LOG_DIR/premarket_start_latest.status.json"
append_trace "wrapper_start" "started" 0

if [ "${SMOKE_SKIP_DEEP_MINI_NOT_FOR_LIVE_SELECTION:-false}" = "true" ]; then
  export ROI_SNIPS_SKIP_DEEP_MINI=true
fi

GROK_REQUIRED="$(env_bool "$ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH")"
DEEP_MINI_REQUIRED="$(env_bool "$ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH")"
if [ "$ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH" = "true" ]; then
  :
fi

append_trace "live_readiness_start" "started" 0
set +e
"$PYTHON_BIN" -m src.workflows.live_readiness --probe-symbol "${ROI_SNIPS_READINESS_PROBE_SYMBOL:-SPY}" \
  > "$LOG_DIR/live_readiness_latest.json" 2> "$LOG_DIR/live_readiness_latest.stderr"
LIVE_READINESS_RC=$?
set -e
write_step_status "$LOG_DIR/live_readiness_latest.status.json" "recorded" "live_readiness" "$LIVE_READINESS_RC" "premarket_research_continues;final_arming_gate_enforces_go_no_go"
append_trace "live_readiness_done" "recorded" "$LIVE_READINESS_RC"

GROK_READINESS_SCRIPT="${ROI_SNIPS_GROK_READINESS_SCRIPT:-scripts/check_grok_research_readiness.sh}"
append_trace "grok_canary_start" "started" 0
set +e
"$GROK_READINESS_SCRIPT" > "$LOG_DIR/grok_research_canary_latest.json" 2> "$LOG_DIR/grok_research_canary_latest.stderr"
GROK_CANARY_RC=$?
GROK_READINESS_RC=$GROK_CANARY_RC
set -e
if [ "$GROK_CANARY_RC" -ne 0 ]; then
  if [ "$GROK_REQUIRED" = "true" ]; then
    write_step_status "$LOG_DIR/grok_research_canary_latest.status.json" "FAIL_REQUIRED_GROK_UNAVAILABLE" "grok_research_readiness" "$GROK_CANARY_RC" "grok_required_but_unavailable"
    append_trace "grok_canary_done" "FAIL_REQUIRED_GROK_UNAVAILABLE" "$GROK_CANARY_RC"
    write_final_status "FAIL" "$GROK_CANARY_RC" "false" "false" "grok_required_but_unavailable"
    append_trace "wrapper_final" "FAIL" "$GROK_CANARY_RC"
    exit "$GROK_CANARY_RC"
  fi
  write_step_status "$LOG_DIR/grok_research_canary_latest.status.json" "WARN_CONTINUE" "grok_research_readiness" "$GROK_CANARY_RC" "optional_grok_readiness_must_not_block_deep_mini_primary_selector"
  append_trace "grok_canary_done" "WARN_CONTINUE" "$GROK_CANARY_RC"
else
  write_step_status "$LOG_DIR/grok_research_canary_latest.status.json" "PASS" "grok_research_readiness" 0 "grok_canary_passed"
  append_trace "grok_canary_done" "PASS" 0
fi

append_trace "grok_pipeline_start" "started" 0
set +e
if [ "${ROI_SNIPS_TEST_STUB_GROK_PIPELINE:-false}" = "true" ]; then
  printf '{"status":"stubbed","step":"grok_research_pipeline","trade_date":"%s"}\n' "$TRADE_DATE" > "$LOG_DIR/grok_heat_latest.json"
  GROK_RESEARCH_RC=0
else
  "$PYTHON_BIN" -m src.workflows.grok_research_pipeline > "$LOG_DIR/grok_heat_latest.json" 2> "$LOG_DIR/grok_heat_latest.stderr"
  GROK_RESEARCH_RC=$?
fi
set -e
if [ "$GROK_RESEARCH_RC" -ne 0 ] && [ "$GROK_REQUIRED" = "true" ]; then
  write_step_status "$LOG_DIR/grok_heat_latest.status.json" "FAIL" "grok_research_pipeline" "$GROK_RESEARCH_RC" "grok_required_pipeline_failed"
  append_trace "grok_pipeline_done" "FAIL" "$GROK_RESEARCH_RC"
  write_final_status "FAIL" "$GROK_RESEARCH_RC" "false" "false" "grok_required_pipeline_failed"
  append_trace "wrapper_final" "FAIL" "$GROK_RESEARCH_RC"
  exit "$GROK_RESEARCH_RC"
fi
write_step_status "$LOG_DIR/grok_heat_latest.status.json" "recorded" "grok_research_pipeline" "$GROK_RESEARCH_RC" "grok_research_only_feeds_deep_mini;final_arming_gate_enforces_deep_mini_ticket"
append_trace "grok_pipeline_done" "recorded" "$GROK_RESEARCH_RC"

append_trace "deep_mini_research_start" "started" 0
set +e
if [ "${ROI_SNIPS_TEST_STUB_RESEARCH_PIPELINE:-false}" = "true" ]; then
  printf '{"status":"stubbed","step":"governed_deep_research_pipeline","trade_date":"%s"}\n' "$TRADE_DATE" > "$LOG_DIR/research_latest.json"
  DEEP_RESEARCH_RC="${ROI_SNIPS_TEST_STUB_RESEARCH_PIPELINE_EXIT_CODE:-0}"
else
  "$PYTHON_BIN" -m src.workflows.research_pipeline > "$LOG_DIR/research_latest.json" 2> "$LOG_DIR/research_latest.stderr"
  DEEP_RESEARCH_RC=$?
fi
set -e
write_step_status "$LOG_DIR/research_latest.status.json" "recorded" "governed_deep_research_pipeline" "$DEEP_RESEARCH_RC" "deep_mini_primary_live_selector;final_arming_gate_enforces_deep_mini_ticket" "true"
append_trace "deep_mini_research_done" "recorded" "$DEEP_RESEARCH_RC"
if [ "$DEEP_RESEARCH_RC" -ne 0 ] && [ "$DEEP_MINI_REQUIRED" = "true" ]; then
  write_step_status "$LOG_DIR/research_latest.status.json" "FAIL" "governed_deep_research_pipeline" "$DEEP_RESEARCH_RC" "deep_mini_required_pipeline_failed" "true"
  write_final_status "FAIL" "$DEEP_RESEARCH_RC" "true" "true" "deep_mini_required_pipeline_failed"
  append_trace "wrapper_final" "FAIL" "$DEEP_RESEARCH_RC"
  exit "$DEEP_RESEARCH_RC"
fi

append_trace "premarket_pipeline_start" "started" 0
set +e
if [ "${ROI_SNIPS_TEST_STUB_PREMARKET_PIPELINE:-false}" = "true" ]; then
  printf '{"status":"stubbed","step":"premarket_pipeline","trade_date":"%s"}\n' "$TRADE_DATE" > "$LOG_DIR/premarket_latest.json"
  PREMARKET_RC=0
else
  "$PYTHON_BIN" -m src.workflows.premarket_pipeline > "$LOG_DIR/premarket_latest.json" 2> "$LOG_DIR/premarket_latest.stderr"
  PREMARKET_RC=$?
fi
set -e
write_step_status "$LOG_DIR/premarket_latest.status.json" "recorded" "premarket_pipeline" "$PREMARKET_RC" "premarket_pipeline_completed"
append_trace "premarket_pipeline_done" "recorded" "$PREMARKET_RC"
if [ "$PREMARKET_RC" -ne 0 ]; then
  write_final_status "FAIL" "$PREMARKET_RC" "true" "true" "premarket_pipeline_failed"
  append_trace "wrapper_final" "FAIL" "$PREMARKET_RC"
  exit "$PREMARKET_RC"
fi

FINAL_STATUS="OK"
if [ "$GROK_CANARY_RC" -ne 0 ] || [ "$GROK_RESEARCH_RC" -ne 0 ]; then
  FINAL_STATUS="DEGRADED_OK_FOR_DEEP_MINI"
fi
write_final_status "$FINAL_STATUS" 0 "true" "true" ""
append_trace "wrapper_final" "$FINAL_STATUS" 0
echo "{\"status\":\"$FINAL_STATUS\",\"mode\":\"live_trade_ready_premarket\",\"generated_at_utc\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"deep_mini_reached\":true}"
exit 0
