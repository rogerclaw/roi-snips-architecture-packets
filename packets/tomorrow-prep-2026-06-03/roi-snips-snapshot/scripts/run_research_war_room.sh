#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INPUT="${1:-${ROOT}/reports/implementation/research_war_room_input.json}"
OUTPUT="${2:-${ROOT}/reports/implementation/research_war_room_output.json}"

cd "$ROOT"
PYTHONPATH=. "${PYTHON:-python3}" -m src.workflows.morning_research_runner --input "$INPUT" --output "$OUTPUT"
