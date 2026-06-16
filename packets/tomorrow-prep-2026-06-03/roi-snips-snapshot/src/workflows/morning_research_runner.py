from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .research_war_room import run_research_war_room


def run_morning_research_from_fixture(input_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    payload = json.loads(input_path.read_text())
    result = run_research_war_room(
        payload.get("events") or [],
        payload.get("tournament_candidates") or [],
        prior_winners=payload.get("prior_winners") or {},
        session=payload.get("session") or {},
    ).to_dict()
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run brokerless Roi Snips morning research war room from local JSON.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = run_morning_research_from_fixture(Path(args.input), Path(args.output))
    print(json.dumps({"status": result["status"], "best_pick": result["best_pick"], "broker_action": "NONE"}, sort_keys=True))
    return 0 if result["status"] in {"PASS", "DEGRADED", "NO_TRADE_RESEARCH_INCOMPLETE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
