from __future__ import annotations

from .top_gainers_scout import scout_top_gainers


def scout_premarket_dollar_volume(rows: list[dict]) -> list[dict]:
    events = scout_top_gainers(rows)
    for event in events:
        event["source_name"] = "external_movers_scout"
        event["catalyst_type"] = "premarket_dollar_volume"
    return events
