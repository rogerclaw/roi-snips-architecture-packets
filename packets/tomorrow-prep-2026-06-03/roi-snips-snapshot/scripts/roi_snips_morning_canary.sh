#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRADE_DATE="${ROI_SNIPS_TRADE_DATE:-$(date +%F)}"
OUTPUT="${ROI_SNIPS_CANARY_OUTPUT:-$ROOT/reports/readiness/canary_${TRADE_DATE}.json}"

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=false
export ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false
export ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT=true
export ROI_SNIPS_SKIP_BROKER_STATE_FOR_SHADOW=true

cd "$ROOT"
"$ROOT/.venv/bin/python" -m src.ops.scheduler_canary --output "$OUTPUT" "$@"
