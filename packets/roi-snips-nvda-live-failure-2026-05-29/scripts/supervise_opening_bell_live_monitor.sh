#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

TRADE_DATE="${ROI_SNIPS_OPENING_BELL_DATE:-$("$PYTHON_BIN" - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo
print(datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"))
PY
)}"
RUN_ID="${ROI_SNIPS_OPENING_RUN_ID:-opening_stream_${TRADE_DATE}_$(date -u +%H%M%S)}"
OUTPUT_DIR="${ROI_SNIPS_OPENING_STREAM_OUTPUT_DIR:-$ROOT_DIR/reports/live_monitor/runs/$RUN_ID}"
MAX_SECONDS="${ROI_SNIPS_OPENING_STREAM_MAX_SECONDS:-900}"
PREFLIGHT_ONLY=false
if [ "${1:-}" = "--preflight-only" ]; then
  PREFLIGHT_ONLY=true
  shift
fi

export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION="${ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION:-false}"

if [ "${ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT:-false}" = "true" ] && [ "$ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION" = "false" ]; then
  echo '{"status":"shadow_preflight_continue","reason":"broker_preflight_skipped_for_no_order_market_data_validation"}'
else
  scripts/check_live_readiness.sh
  TMP_PARENT="${TMPDIR:-/tmp}"
  mkdir -p "$TMP_PARENT"
  OPENING_READINESS_JSON="$(mktemp "$TMP_PARENT/roi-snips-opening-readiness.XXXXXXXX.json")"
  cleanup_opening_readiness_json() {
    rm -f "$OPENING_READINESS_JSON" 2>/dev/null || true
  }
  trap cleanup_opening_readiness_json EXIT
  if ! scripts/check_opening_bell_readiness.sh >"$OPENING_READINESS_JSON"; then
    cat "$OPENING_READINESS_JSON"
    if [ "$ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION" = "false" ]; then
      echo '{"status":"shadow_preflight_continue","reason":"opening_bell_readiness_not_green_without_live_order_env"}'
    elif "$PYTHON_BIN" - "$OPENING_READINESS_JSON" <<'PY'
import json
import sys

path = sys.argv[1]
payload = json.loads(open(path).read())
readiness = payload.get("readiness") or {}
candidate = payload.get("candidate_specific_readiness") or {}
session_phase = readiness.get("session_phase")
blockers = list(payload.get("opening_bell_blockers") or []) + list(candidate.get("blockers") or [])
if session_phase == "PRE_ENTRY" and blockers and all(str(item).endswith(":no_immediately_available_entry_mode") or str(item) == "no_immediately_available_entry_mode" for item in blockers):
    raise SystemExit(0)
raise SystemExit(1)
PY
    then
      echo '{"status":"live_pre_entry_stream_continue","reason":"only_pre_entry_no_immediate_mode_blockers"}'
    else
      exit 1
    fi
  fi
  cleanup_opening_readiness_json
  trap - EXIT
fi

if [ "$PREFLIGHT_ONLY" = "true" ]; then
  exit 0
fi

RUN_CONTINUATION="${ROI_SNIPS_RUN_CONTINUATION_MONITOR:-}"
if [ -z "$RUN_CONTINUATION" ]; then
  if [ "$ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION" = "true" ]; then
    RUN_CONTINUATION="true"
  else
    RUN_CONTINUATION="false"
  fi
fi

continuation_delay_seconds() {
  "$PYTHON_BIN" - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo

continuation_monitor_start_et = "09:35:00"
tz = ZoneInfo("America/New_York")
now = datetime.now(tz)
hour, minute, second = [int(part) for part in continuation_monitor_start_et.split(":")]
target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
print(max(0, int((target - now).total_seconds())))
PY
}

CONTINUATION_PID=""
if [ "$RUN_CONTINUATION" = "true" ]; then
  (
    delay="$(continuation_delay_seconds)"
    if [ "$delay" -gt 0 ]; then
      sleep "$delay"
    fi
    exec scripts/run_opening_bell_live_monitor.sh --loop-only
  ) &
  CONTINUATION_PID="$!"
fi

cleanup_continuation() {
  if [ -n "$CONTINUATION_PID" ] && kill -0 "$CONTINUATION_PID" 2>/dev/null; then
    kill "$CONTINUATION_PID" 2>/dev/null || true
  fi
}
trap cleanup_continuation INT TERM

set +e
"$PYTHON_BIN" -m src.workflows.opening_stream_supervisor \
  --live \
  --candidates-from-morning \
  --max-seconds "$MAX_SECONDS" \
  --output-dir "$OUTPUT_DIR"
stream_rc=$?
set -e

if [ "$stream_rc" -ne 0 ]; then
  cleanup_continuation
  exit "$stream_rc"
fi

if [ -n "$CONTINUATION_PID" ]; then
  wait "$CONTINUATION_PID"
fi
