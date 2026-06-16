#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.workflows.grok_d_research_bridge import run_governed_grok_d_research


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a brokerless Grok-first D-research canary from local shortlist JSON.")
    parser.add_argument("--shortlist-json", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    shortlist = json.loads(Path(args.shortlist_json).read_text())
    result = run_governed_grok_d_research(
        shortlist if isinstance(shortlist, list) else [],
        {"canary": True, "broker_action": "NONE"},
        Path(args.output_dir),
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.success and result.structured_packet else 1


if __name__ == "__main__":
    raise SystemExit(main())
