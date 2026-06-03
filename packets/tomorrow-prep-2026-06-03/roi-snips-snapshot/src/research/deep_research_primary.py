from __future__ import annotations

from pathlib import Path


PROMPT_PATH = Path("docs/prompts/rebuild/DEEP_RESEARCH_SINGLE_BEST_TRADE.md")


def load_deep_research_prompt(repo_root: Path) -> str:
    return (repo_root / PROMPT_PATH).read_text()


def render_deep_research_prompt(repo_root: Path, *, trading_date: str, seed_packet_json: str) -> str:
    prompt = load_deep_research_prompt(repo_root).replace("{trading_date}", trading_date)
    return f"{prompt}\n\nSEED PACKET JSON:\n{seed_packet_json}\n"
