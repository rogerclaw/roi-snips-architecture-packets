from __future__ import annotations

from .common import raw_event


def scout_top_gainers(rows: list[dict]) -> list[dict]:
    return [
        raw_event(
            source_name="premarket_gapper_scout",
            source_tier=2,
            source_url=str(row.get("source_url") or "local://top-gainers"),
            headline=str(row.get("headline") or f"{row.get('ticker')} premarket top gainer"),
            raw_text=str(row.get("raw_text") or row.get("headline") or ""),
            company_name=row.get("company"),
            ticker_candidates=[str(row.get("ticker"))],
            catalyst_type="top_premarket_gainer",
            official_flag=False,
            structured_flag=True,
            social_flag=False,
            credibility_score_initial=6.5,
            extraction_confidence=0.85,
        ).to_dict()
        for row in rows
        if row.get("ticker")
    ]
