#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

RUNNING_STREAMS="$(ps -axo pid=,command= | awk '$0 ~ /src[.]workflows[.]opening_stream_supervisor/ && $0 ~ /--live/ {print $1 " " substr($0, index($0,$2))}')"
if [ -n "$RUNNING_STREAMS" ]; then
  export RUNNING_STREAMS
  "$PYTHON_BIN" - <<'PY'
import json
import os

print(json.dumps({
    "status": "blocked",
    "reason": "opening_stream_already_running",
    "orders_allowed": False,
    "orders_submitted": False,
    "pid_summary": os.environ.get("RUNNING_STREAMS", "").splitlines(),
}))
PY
  exit 2
fi

export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=false
export ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false
export ROI_SNIPS_RUN_CONTINUATION_MONITOR=true
export ROI_SNIPS_OPENING_STREAM_MAX_SECONDS="${ROI_SNIPS_OPENING_STREAM_MAX_SECONDS:-900}"

# This scheduled validation proves market-data/orchestration behavior only.
# It must not query or mutate live broker order/account/position state.
export ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT=true
export ROI_SNIPS_SKIP_BROKER_STATE_FOR_SHADOW=true

exec scripts/supervise_opening_bell_live_monitor.sh "$@"
