#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 '<COMMAND>'  # e.g. STATUS | DISABLE NEW ENTRIES | ENABLE NEW ENTRIES | FLAT ALL NOW | EXECUTE ENTRY <plan_id>'" >&2
  exit 1
fi

"$PYTHON_BIN" -m src.approval.command_processor "$@"
