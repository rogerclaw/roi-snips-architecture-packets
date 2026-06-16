from __future__ import annotations

from .common import raw_event


def scout_social_velocity(rows: list[dict]) -> list[dict]:
    return [
        raw_event(
            source_name=str(row.get("source_name") or "grok_x"),
            source_tier=3,
            source_url=str(row.get("source_url") or "local://social-velocity"),
            headline=str(row.get("headline") or f"{row.get('ticker')} social velocity spike"),
            raw_text=str(row.get("raw_text") or row.get("headline") or ""),
            company_name=row.get("company"),
            ticker_candidates=[str(row.get("ticker"))],
            catalyst_type="social_velocity",
            official_flag=False,
            structured_flag=False,
            social_flag=True,
            credibility_score_initial=5.5,
            extraction_confidence=0.75,
        ).to_dict()
        for row in rows
        if row.get("ticker")
    ]
