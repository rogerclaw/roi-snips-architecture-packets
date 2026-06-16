from __future__ import annotations

from typing import Any


def select_theme_sympathy(raw_candidates: list[dict[str, Any]], leader: str | None = None) -> list[dict[str, Any]]:
    leader_symbol = str(leader or "").upper()
    rows = []
    for row in raw_candidates:
        symbol = str(row.get("ticker") or "").upper()
        buckets = set(row.get("raw_buckets") or [])
        flags = set(row.get("pre_filter_flags") or [])
        if symbol == leader_symbol:
            continue
        if buckets.intersection({"sector_sympathy_movers", "government_contract_policy_names", "fda_biotech_names"}) or flags.intersection({"official_catalyst", "structured_catalyst"}):
            rows.append(row)
    rows.sort(key=lambda row: (len(row.get("raw_buckets") or []), float(row.get("premarket_dollar_volume") or 0.0)), reverse=True)
    return rows


class ThemeSympathyScout:
    def collect_from_raw(self, raw_candidates: list[dict[str, Any]], leader: str | None = None) -> list[dict[str, Any]]:
        return select_theme_sympathy(raw_candidates, leader=leader)
