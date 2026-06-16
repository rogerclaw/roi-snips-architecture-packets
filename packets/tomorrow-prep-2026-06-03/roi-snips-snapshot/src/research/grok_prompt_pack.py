from __future__ import annotations

from pathlib import Path

from ..common.config import repo_root


CURRENT_HYBRID_PROMPT_FILENAMES = [
    "04_GROK_CANDIDATE_DISCOVERY_TOURNAMENT.md",
    "06_GROK_TICKET_INPUT_SUMMARY.md",
]

OBSOLETE_GROK_AUTHORIZER_PROMPT_FILENAMES = [
    "04_GROK_D_RESEARCH_TOURNAMENT.md",
    "06_GROK_TRADE_AUTHORIZATION_TICKET.md",
]


def prompt_pack_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "docs" / "prompts" / "grok_first"


def load_grok_prompt_pack(root: Path | None = None) -> dict[str, str]:
    base = prompt_pack_dir(root)
    return {name: (base / name).read_text() for name in CURRENT_HYBRID_PROMPT_FILENAMES}


def prompt_pack_status(root: Path | None = None) -> dict[str, object]:
    base = prompt_pack_dir(root)
    missing = [name for name in CURRENT_HYBRID_PROMPT_FILENAMES if not (base / name).exists()]
    obsolete_present = [name for name in OBSOLETE_GROK_AUTHORIZER_PROMPT_FILENAMES if (base / name).exists()]
    return {
        "ok": not missing,
        "directory": str(base),
        "required": CURRENT_HYBRID_PROMPT_FILENAMES,
        "missing": missing,
        "old_grok_authorizer_prompts_required": False,
        "obsolete_present": obsolete_present,
    }
