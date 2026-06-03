from __future__ import annotations

from typing import Any


def select_premarket_gappers(raw_candidates: list[dict[str, Any]], *, min_gap_pct: float = 5.0) -> list[dict[str, Any]]:
    rows = [row for row in raw_candidates if abs(float(row.get("gap_pct") or 0.0)) >= min_gap_pct]
    rows.sort(key=lambda row: (abs(float(row.get("gap_pct") or 0.0)), float(row.get("premarket_dollar_volume") or 0.0)), reverse=True)
    return rows


class PremarketGapperScout:
    def collect_from_raw(self, raw_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return select_premarket_gappers(raw_candidates)
