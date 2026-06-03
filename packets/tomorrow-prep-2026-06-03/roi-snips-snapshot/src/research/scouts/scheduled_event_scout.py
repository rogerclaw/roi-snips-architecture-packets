from __future__ import annotations

from .common import raw_event


def scout_scheduled_events(rows: list[dict]) -> list[dict]:
    return [
        raw_event(
            source_name="scheduled_event_scout",
            source_tier=2,
            source_url=str(row.get("source_url") or "local://scheduled-event"),
            headline=str(row.get("headline") or f"{row.get('ticker')} scheduled catalyst today"),
            raw_text=str(row.get("raw_text") or row.get("headline") or ""),
            company_name=row.get("company"),
            ticker_candidates=[str(row.get("ticker"))],
            catalyst_type=str(row.get("catalyst_type") or "scheduled_event"),
            official_flag=bool(row.get("official_flag", False)),
            structured_flag=True,
            social_flag=False,
            credibility_score_initial=7.0,
            extraction_confidence=0.85,
        ).to_dict()
        for row in rows
        if row.get("ticker")
    ]
