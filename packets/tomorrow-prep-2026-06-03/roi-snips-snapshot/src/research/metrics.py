from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_run(events: list[dict[str, Any]], clusters: list[dict[str, Any]], shortlisted: list[dict[str, Any]], eliminated: list[dict[str, Any]]) -> dict[str, Any]:
    event_counter = Counter(event.get("source_name") for event in events)
    elimination_counter = Counter()
    for item in eliminated:
        for reason in (item.get("gate_result") or {}).get("reasons") or []:
            elimination_counter[reason] += 1
    return {
        "raw_events_count": len(events),
        "raw_events_by_source": dict(event_counter),
        "candidate_clusters_count": len(clusters),
        "shortlisted_count": len(shortlisted),
        "eliminated_count": len(eliminated),
        "elimination_reasons": dict(elimination_counter),
    }
