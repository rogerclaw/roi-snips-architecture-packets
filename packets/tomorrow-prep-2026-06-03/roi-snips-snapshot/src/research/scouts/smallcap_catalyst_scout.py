from __future__ import annotations

from .common import raw_event


def scout_smallcap_catalysts(rows: list[dict]) -> list[dict]:
    return [
        raw_event(
            source_name=str(row.get("source_name") or "smallcap_catalyst_scout"),
            source_tier=1,
            source_url=str(row.get("source_url") or "local://smallcap-catalyst"),
            headline=str(row.get("headline") or f"{row.get('ticker')} fresh catalyst"),
            raw_text=str(row.get("raw_text") or row.get("headline") or ""),
            company_name=row.get("company"),
            ticker_candidates=[str(row.get("ticker"))],
            catalyst_type=str(row.get("catalyst_type") or "smallcap_catalyst"),
            official_flag=bool(row.get("official_flag", True)),
            structured_flag=bool(row.get("structured_flag", True)),
            social_flag=False,
            credibility_score_initial=8.0,
            extraction_confidence=0.9,
        ).to_dict()
        for row in rows
        if row.get("ticker")
    ]
