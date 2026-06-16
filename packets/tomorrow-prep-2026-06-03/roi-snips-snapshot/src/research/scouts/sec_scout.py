from __future__ import annotations

from typing import Any

from ...adapters.sec_edgar import SecEdgarAdapter
from .common import raw_event


FORM_CATALYST_MAP = {
    "8-K": "earnings_or_material_update",
    "13D": "activist_or_ownership",
    "13G": "ownership",
    "SC 13D": "activist_or_ownership",
    "SC 13G": "ownership",
    "S-4": "mna_or_reorg",
    "425": "mna_or_reorg",
    "DEFM14A": "mna_or_reorg",
    "SC TO": "tender_offer",
    "6-K": "foreign_issuer_update",
}


class SecScout:
    def __init__(self, adapter: SecEdgarAdapter | None = None) -> None:
        self.adapter = adapter or SecEdgarAdapter()

    def collect(self, tickers: list[str]) -> list[dict[str, Any]]:
        res = self.adapter.fetch_recent_filings(tickers, forms_allow={*FORM_CATALYST_MAP.keys(), "10-Q", "10-K", "S-3"}, per_ticker_limit=12)
        if not res.get("ok"):
            return []
        events = []
        for filing in res.get("filings") or []:
            form = str(filing.get("form") or "").upper()
            ticker = str(filing.get("ticker") or "").upper()
            event = raw_event(
                source_name="sec_edgar",
                source_tier=0,
                source_url=str(filing.get("edgar_url") or "https://www.sec.gov"),
                headline=f"{ticker} {form} filing",
                raw_text=f"SEC filing {form} for {ticker}",
                company_name=ticker,
                ticker_candidates=[ticker],
                catalyst_type=FORM_CATALYST_MAP.get(form, "filing_update"),
                official_flag=True,
                structured_flag=False,
                social_flag=False,
                credibility_score_initial=9.0,
                extraction_confidence=0.95,
                published_at=filing.get("filing_date"),
                updated_at=filing.get("filing_date"),
                notes=[f"form={form}", f"accession={filing.get('accession')}"] if filing.get("accession") else [f"form={form}"],
            )
            events.append(event.to_dict())
        return events
