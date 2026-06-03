#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRADE_DATE="${ROI_SNIPS_TRADE_DATE:-$(date +%F)}"
CANARY="$ROOT/reports/readiness/canary_${TRADE_DATE}.json"
READINESS="$ROOT/reports/readiness/morning_readiness_${TRADE_DATE}.json"

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=false
export ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false
export ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT=true
export ROI_SNIPS_SKIP_BROKER_STATE_FOR_SHADOW=true

cd "$ROOT"
"$ROOT/.venv/bin/python" -m src.ops.scheduler_canary --output "$CANARY"
"$ROOT/.venv/bin/python" scripts/run_next_open_shadow_validation.py "$@"
"$ROOT/.venv/bin/python" -m src.ops.morning_control_plane --date "$TRADE_DATE" --output "$READINESS"
