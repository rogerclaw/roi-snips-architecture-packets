#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3.11}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3.11 not found. Set PYTHON_BIN to a compatible interpreter." >&2
  exit 1
fi

"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo "Roi Snips environment bootstrapped in $ROOT_DIR/.venv"
