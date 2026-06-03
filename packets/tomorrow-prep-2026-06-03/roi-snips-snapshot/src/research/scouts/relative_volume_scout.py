from __future__ import annotations

from typing import Any


def select_high_relative_volume(raw_candidates: list[dict[str, Any]], *, min_dollar_volume: float = 1_000_000) -> list[dict[str, Any]]:
    rows = [row for row in raw_candidates if float(row.get("premarket_dollar_volume") or 0.0) >= min_dollar_volume]
    rows.sort(key=lambda row: float(row.get("premarket_dollar_volume") or 0.0), reverse=True)
    return rows


class RelativeVolumeScout:
    def collect_from_raw(self, raw_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return select_high_relative_volume(raw_candidates)
