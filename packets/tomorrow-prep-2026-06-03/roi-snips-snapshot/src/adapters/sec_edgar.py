"""SEC EDGAR ingestion adapter using data.sec.gov JSON APIs."""

from __future__ import annotations

import os
from typing import Any

from ..common.http_utils import http_get_json


class SecEdgarAdapter:
    def __init__(self, user_agent: str | None = None) -> None:
        self.user_agent = user_agent or os.getenv("SEC_EDGAR_USER_AGENT") or "roi-snips/1.0 (+ops@example.com)"
        self.base_url = "https://data.sec.gov"

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent, "Accept": "application/json"}

    def fetch_ticker_map(self) -> dict[str, Any]:
        url = "https://www.sec.gov/files/company_tickers.json"
        res = http_get_json(url, headers=self._headers())
        if not res.ok:
            return {"ok": False, "reason": "sec_ticker_map_failed", "status": res.status, "error": res.error}

        raw = res.data or {}
        mapping: dict[str, str] = {}
        for _, row in raw.items() if isinstance(raw, dict) else []:
            t = str(row.get("ticker", "")).upper()
            c = str(row.get("cik_str", "")).strip()
            if t and c:
                mapping[t] = c.zfill(10)
        return {"ok": True, "mapping": mapping}

    def fetch_recent_filings(
        self,
        tickers: list[str],
        forms_allow: set[str] | None = None,
        per_ticker_limit: int = 20,
    ) -> dict[str, Any]:
        forms_allow = forms_allow or {"8-K", "10-Q", "10-K", "S-1", "S-3", "13D", "13G", "SC 13D", "SC 13G"}

        ticker_map_res = self.fetch_ticker_map()
        if not ticker_map_res.get("ok"):
            return ticker_map_res
        ticker_map = ticker_map_res["mapping"]

        filings: list[dict[str, Any]] = []
        for ticker in sorted(set(t.upper() for t in tickers if t)):
            cik = ticker_map.get(ticker)
            if not cik:
                continue
            url = f"{self.base_url}/submissions/CIK{cik}.json"
            res = http_get_json(url, headers=self._headers())
            if not res.ok:
                filings.append({"ticker": ticker, "error": res.error, "status": res.status})
                continue

            recent = ((res.data or {}).get("filings") or {}).get("recent") or {}
            forms = recent.get("form") or []
            dates = recent.get("filingDate") or []
            accessions = recent.get("accessionNumber") or []
            prim_docs = recent.get("primaryDocument") or []

            n = min(len(forms), len(dates), len(accessions), len(prim_docs), per_ticker_limit)
            for i in range(n):
                form = str(forms[i]).upper()
                if form not in forms_allow:
                    continue
                accession = str(accessions[i]).replace("-", "")
                filings.append(
                    {
                        "ticker": ticker,
                        "form": forms[i],
                        "filing_date": dates[i],
                        "accession": accessions[i],
                        "primary_document": prim_docs[i],
                        "edgar_url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{prim_docs[i]}",
                    }
                )

        return {"ok": True, "count": len(filings), "filings": filings}
