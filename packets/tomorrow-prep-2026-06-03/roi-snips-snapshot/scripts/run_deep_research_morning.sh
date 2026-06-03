#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec "${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}" -m src.workflows.deep_research_morning "$@"
