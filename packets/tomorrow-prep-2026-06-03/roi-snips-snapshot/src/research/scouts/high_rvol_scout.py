from __future__ import annotations

from .top_gainers_scout import scout_top_gainers


def scout_high_rvol(rows: list[dict]) -> list[dict]:
    events = scout_top_gainers(rows)
    for event in events:
        event["source_name"] = "relative_volume_scout"
        event["catalyst_type"] = "high_relative_volume"
    return events
