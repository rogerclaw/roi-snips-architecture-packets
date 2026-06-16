#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Assert brokerless no-order morning readiness proof is ready.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--readiness-json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    path = Path(args.readiness_json) if args.readiness_json else root / "reports" / "readiness" / f"morning_readiness_{args.date}.json"
    payload = json.loads(path.read_text())
    if not payload.get("ready_for_no_order"):
        print(json.dumps({"ready": False, "failure_reasons": payload.get("failure_reasons", []), "path": str(path)}, sort_keys=True))
        return 1
    if payload.get("ready_for_live") or payload.get("ready_for_paper"):
        print(json.dumps({"ready": False, "failure_reasons": ["unexpected_live_or_paper_ready"], "path": str(path)}, sort_keys=True))
        return 1
    print(json.dumps({"ready": True, "path": str(path), "final_status": payload.get("final_status")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
