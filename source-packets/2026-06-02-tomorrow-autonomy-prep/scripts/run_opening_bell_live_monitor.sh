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
LOG_DIR="${ROI_SNIPS_OPENING_BELL_LOG_DIR:-$ROOT_DIR/reports/live_monitor}"
LOG_FILE="${ROI_SNIPS_OPENING_BELL_LOG_FILE:-$LOG_DIR/opening_bell_live_${TRADE_DATE}.jsonl}"
POLL_SECONDS="${ROI_SNIPS_MONITOR_POLL_SECONDS:-2}"
MAX_ITERATIONS="${ROI_SNIPS_OPENING_BELL_MAX_ITERATIONS:-3600}"

mkdir -p "$LOG_DIR"

emit() {
  "$PYTHON_BIN" - "$@" <<'PY' >> "$LOG_FILE"
import json
import sys
from datetime import datetime, timezone

event = {"ts_utc": datetime.now(timezone.utc).isoformat(), "event": sys.argv[1]}
if len(sys.argv) > 2:
    event["detail"] = sys.argv[2]
print(json.dumps(event, sort_keys=True))
PY
}

et_seconds_until_entry_end() {
  "$PYTHON_BIN" - <<'PY'
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.common.config import load_live_config

cfg = load_live_config()
session = cfg.get("session") or cfg.get("schedule") or {}
tz = ZoneInfo(session.get("timezone", "America/New_York"))
end_raw = str(session.get("last_new_entry_et", session.get("no_new_symbols_after", "11:00:00")))
parts = [int(part) for part in end_raw.split(":")]
while len(parts) < 3:
    parts.append(0)
now = datetime.now(tz)
end = now.replace(hour=parts[0], minute=parts[1], second=parts[2], microsecond=0)
if now > end:
    print(0)
else:
    print(max(0, int((end - now).total_seconds())))
PY
}

preflight() {
  export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION="${ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION:-true}"
  export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

  emit "preflight_start" "live_readiness"
  scripts/check_live_readiness.sh >> "$LOG_FILE"
  emit "preflight_complete" "live_readiness"

  emit "preflight_start" "opening_bell_readiness"
  scripts/check_opening_bell_readiness.sh >> "$LOG_FILE"
  emit "preflight_complete" "opening_bell_readiness"
}

run_loop() {
  export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION="${ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION:-true}"
  export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

  emit "live_monitor_loop_start" "$LOG_FILE"
  i=0
  while [ "$i" -lt "$MAX_ITERATIONS" ]; do
    remaining="$(et_seconds_until_entry_end)"
    if [ "$remaining" -le 0 ]; then
      emit "live_monitor_loop_stop" "entry_window_ended"
      break
    fi
    emit "live_monitor_iteration_start" "iteration=$i"
    set +e
    "$PYTHON_BIN" -m src.workflows.live_monitor >> "$LOG_FILE" 2>&1
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
      emit "live_monitor_iteration_error" "iteration=$i rc=$rc"
    else
      emit "live_monitor_iteration_complete" "iteration=$i"
    fi
    i=$((i + 1))
    sleep "$POLL_SECONDS"
  done
  emit "live_monitor_loop_complete" "iterations=$i"
}

case "${1:-}" in
  --preflight-only)
    preflight
    ;;
  --loop-only)
    run_loop
    ;;
  "")
    preflight
    run_loop
    ;;
  *)
    echo "usage: $0 [--preflight-only|--loop-only]" >&2
    exit 2
    ;;
esac

echo "$LOG_FILE"
