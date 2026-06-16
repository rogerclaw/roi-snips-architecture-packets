from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


QUERY_FAMILIES: dict[str, list[str]] = {
    "general_premarket": [
        "premarket movers unusual volume today small cap",
        "highest premarket volume gainers today",
        "stocks up premarket catalyst today",
        "small cap stock up premarket why today",
        "high relative volume stocks premarket today",
    ],
    "government_policy_contract": [
        "small cap government contract award stock today",
        "stock government funding award premarket today",
        "CHIPS Act funding stock premarket",
        "Department of Commerce funding stock ticker today",
        "SAM.gov award public company stock today",
    ],
    "biotech_fda": [
        "FDA approval stock premarket today",
        "medical device clearance stock today",
        "biotech trial results stock up premarket",
        "clinical trial data stock premarket today",
    ],
    "mna_strategic_review": [
        "merger acquisition stock up premarket today",
        "strategic alternatives stock premarket today",
        "takeover rumor stock today confirmed",
    ],
    "product_partnership": [
        "product launch stock up premarket today",
        "partnership announcement stock premarket today",
        "contract win stock premarket today",
    ],
}


TICKER_ENRICHMENT_TEMPLATES = [
    "{ticker} stock why up today",
    "{ticker} press release today",
    "{ticker} 8-K today",
    "{ticker} investor event today",
    "{ticker} StockTwits trending",
    "{ticker} Reddit today",
    "${ticker} X today catalyst",
]


@dataclass(frozen=True)
class QueryRecord:
    family: str
    query: str
    ticker: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {"family": self.family, "query": self.query, "ticker": self.ticker}


def generate_broad_queries(families: Iterable[str] | None = None) -> list[QueryRecord]:
    selected = list(families or QUERY_FAMILIES.keys())
    rows: list[QueryRecord] = []
    seen: set[str] = set()
    for family in selected:
        for query in QUERY_FAMILIES.get(family, []):
            key = query.lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append(QueryRecord(family=family, query=query))
    return rows


def generate_ticker_enrichment_queries(ticker: str) -> list[QueryRecord]:
    symbol = str(ticker or "").upper().strip()
    if not symbol:
        return []
    out: list[QueryRecord] = []
    seen: set[str] = set()
    for template in TICKER_ENRICHMENT_TEMPLATES:
        query = template.format(ticker=symbol)
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(QueryRecord(family="ticker_specific_enrichment", query=query, ticker=symbol))
    return out


def generate_query_plan(tickers: Iterable[str] = ()) -> list[dict[str, str | None]]:
    records = generate_broad_queries()
    for ticker in tickers:
        records.extend(generate_ticker_enrichment_queries(ticker))
    return [record.to_dict() for record in records]
