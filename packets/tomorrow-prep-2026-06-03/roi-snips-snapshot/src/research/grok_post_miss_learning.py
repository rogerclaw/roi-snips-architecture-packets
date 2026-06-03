from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_post_miss_learning(
    *,
    actual_runners: list[dict[str, Any]],
    grok_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    picked = {str(row.get("ticker") or row.get("symbol") or "").upper() for row in grok_candidates}
    missed = [row for row in actual_runners if str(row.get("ticker") or row.get("symbol") or "").upper() not in picked]
    return {
        "stage": "post_miss_learning",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "missed_runners": missed,
        "source_failures": [],
        "query_updates": [f"${str(row.get('ticker') or row.get('symbol')).upper()} why up" for row in missed if row.get("ticker") or row.get("symbol")],
        "handle_list_updates": [],
        "scoring_updates": ["raise weight for first-seen X clusters that later receive hard-source confirmation"] if missed else [],
        "next_day_lessons": ["Backtest missed runners against X heat and web verification before adding handles blindly."] if missed else [],
    }
