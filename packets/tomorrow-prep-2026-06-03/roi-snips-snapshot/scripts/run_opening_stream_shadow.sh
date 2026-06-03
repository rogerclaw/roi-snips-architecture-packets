#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=false
export ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=false
export ROI_SNIPS_SHADOW_SKIP_BROKER_PREFLIGHT=true
export ROI_SNIPS_SKIP_BROKER_STATE_FOR_SHADOW=true
export ROI_SNIPS_RUN_CONTINUATION_MONITOR=true

exec scripts/supervise_opening_bell_live_monitor.sh "$@"
