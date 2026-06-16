from __future__ import annotations

import argparse
import json
from datetime import datetime

from ..common.config import repo_root
from ..research.deep_research_primary import render_deep_research_prompt
from ..research.research_seed_packet import build_research_seed_packet
from ..research.storage import ResearchRunStorage


def build_morning_seed_and_prompt(trading_date: str | None = None) -> dict[str, str]:
    storage = ResearchRunStorage(trading_day=trading_date or datetime.now().strftime("%Y-%m-%d"))
    seed = build_research_seed_packet(trading_date=storage.trading_day)
    seed_path = storage.write_json("research_seed_packet.json", seed)
    prompt = render_deep_research_prompt(repo_root(), trading_date=storage.trading_day, seed_packet_json=json.dumps(seed, indent=2, sort_keys=True))
    prompt_path = storage.path("deep_research_single_best_trade_prompt.txt")
    prompt_path.write_text(prompt)
    return {"research_seed_packet": str(seed_path), "prompt": str(prompt_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the deep-research-first morning seed packet and prompt.")
    parser.add_argument("--trading-date")
    args = parser.parse_args()
    print(json.dumps(build_morning_seed_and_prompt(args.trading_date), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
