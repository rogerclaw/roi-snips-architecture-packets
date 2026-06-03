#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.workflows.clean_rebuild import run_clean_rebuild_shadow


def main() -> int:
    parser = argparse.ArgumentParser(description="Run brokerless Roi Snips clean-rebuild shadow workflow.")
    parser.add_argument("--candidates-json", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--tape-json", help="Optional local tape snapshot JSON for brokerless routing.")
    args = parser.parse_args()

    candidates = json.loads(Path(args.candidates_json).read_text())
    tape = json.loads(Path(args.tape_json).read_text()) if args.tape_json else None
    result = run_clean_rebuild_shadow(candidates, tape)
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps({"ready": result["ready"], "output_json": args.output_json}, sort_keys=True))
    return 0 if result["artifact_gate"]["no_order_attestation"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
