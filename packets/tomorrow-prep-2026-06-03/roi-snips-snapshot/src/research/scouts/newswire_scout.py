from __future__ import annotations

from ...adapters.benzinga_news import BenzingaNewsAdapter
from .common import raw_event


class NewswireScout:
    def __init__(self, adapter: BenzingaNewsAdapter | None = None) -> None:
        self.adapter = adapter or BenzingaNewsAdapter()

    def collect(self, tickers: list[str] | None = None) -> list[dict[str, object]]:
        tickers_csv = None
        if tickers:
            cleaned = sorted({str(t).upper() for t in tickers if str(t).strip()})
            tickers_csv = ",".join(cleaned) if cleaned else None
        res = self.adapter.fetch_events(page_size=100, tickers=tickers_csv)
        if not res.get("ok"):
            return []
        out = []
        for item in res.get("events") or []:
            symbols = [str(t).upper() for t in (item.get("tickers") or []) if str(t).strip()]
            if not symbols:
                continue
            channels = [str(ch) for ch in (item.get("channels") or [])]
            title = str(item.get("title") or "")
            lowered = title.lower()
            catalyst_type = "structured_news"
            if any(k in lowered for k in ["department of commerce", "commerce department", "chips", "government grant", "federal contract", "contract award", "government equity", "equity stake"]):
                catalyst_type = "government_contract"
            elif any(k in lowered for k in ["earnings", "guidance", "beat", "miss"]):
                catalyst_type = "earnings_or_guidance"
            elif any(k in lowered for k in ["acquire", "merger", "buyout", "takeover"]):
                catalyst_type = "mna_or_reorg"
            elif any(k in lowered for k in ["approval", "fda", "phase", "trial"]):
                catalyst_type = "medical_or_biotech"
            elif any(k in lowered for k in ["launch", "partnership", "contract", "deal", "award"]):
                catalyst_type = "product_or_partnership"
            elif any(k in lowered for k in ["surges", "jumps", "soars", "spikes", "gainers", "movers"]):
                catalyst_type = "exchange_mover"
            event = raw_event(
                source_name="benzinga_newswire",
                source_tier=1,
                source_url=str(item.get("url") or "https://api.benzinga.com"),
                headline=title,
                raw_text=title,
                company_name=None,
                ticker_candidates=symbols,
                catalyst_type=catalyst_type,
                official_flag=False,
                structured_flag=True,
                social_flag=False,
                credibility_score_initial=7.5,
                extraction_confidence=0.85,
                published_at=item.get("created") or item.get("updated"),
                updated_at=item.get("updated") or item.get("created"),
                notes=channels,
            )
            out.append(event.to_dict())
        return out
