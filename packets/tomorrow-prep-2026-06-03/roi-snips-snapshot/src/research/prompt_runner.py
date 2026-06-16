from __future__ import annotations

from pathlib import Path
from typing import Any


def load_rebuild_prompt(name: str, *, root: Path | None = None) -> str:
    base = root or Path(__file__).resolve().parents[2] / "docs" / "prompts" / "rebuild"
    path = base / name
    return path.read_text()


def build_prompt_packet(prompt_names: list[str], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    return {
        "status": "PROMPTS_LOADED",
        "prompt_count": len(prompt_names),
        "prompts": [{"name": name, "body": load_rebuild_prompt(name)} for name in prompt_names],
        "context": context,
    }
