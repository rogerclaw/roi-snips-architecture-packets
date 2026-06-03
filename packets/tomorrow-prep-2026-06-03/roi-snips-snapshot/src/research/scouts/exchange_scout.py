from __future__ import annotations

from typing import Any

from ...adapters.alpaca_news import AlpacaNewsAdapter
from ...adapters.benzinga_news import BenzingaNewsAdapter
from ...common.provider_factory import build_market_data_adapter
from ..market_overlay import build_overlay_for_symbol
from .common import raw_event


MOVER_KEYWORDS = ["surges", "jumps", "soars", "spikes", "gainers", "movers", "breakout", "active", "volume", "unusual"]
CATALYST_MAP = {
    "earnings_or_guidance": ["earnings", "guidance", "beat", "miss", "raises", "lowers"],
    "mna_or_reorg": ["acquire", "acquisition", "merger", "buyout", "takeover", "strategic alternatives"],
    "medical_or_biotech": ["approval", "fda", "phase", "trial", "clearance"],
    "product_or_partnership": ["launch", "partnership", "contract", "deal", "award", "collaboration"],
    "financing_or_balance_sheet": ["offering", "financing", "debt", "convertible", "private placement"],
}


class ExchangeScout:
    def __init__(
        self,
        benzinga: BenzingaNewsAdapter | None = None,
        alpaca_news: AlpacaNewsAdapter | None = None,
        md: Any | None = None,
    ) -> None:
        self.benzinga = benzinga or BenzingaNewsAdapter()
        self.alpaca_news = alpaca_news or AlpacaNewsAdapter()
        self.md = md or build_market_data_adapter()

    def _normalized_tickers_csv(self, tickers: list[str] | None) -> str | None:
        if not tickers:
            return None
        cleaned = sorted({str(t).upper() for t in tickers if str(t).strip()})
        return ",".join(cleaned) if cleaned else None

    def _classify(self, title: str, summary: str = "", channels: list[str] | None = None) -> tuple[str, bool, float]:
        text = f"{title} {summary}".lower()
        lowered_channels = [str(ch).lower() for ch in (channels or [])]
        looks_like_mover = any(word in text for word in MOVER_KEYWORDS) or any("market" in ch or "technical" in ch for ch in lowered_channels)
        catalyst_type = "exchange_mover"
        catalyst_bonus = 0.0
        for label, keywords in CATALYST_MAP.items():
            if any(keyword in text for keyword in keywords):
                catalyst_type = label
                catalyst_bonus = 0.4
                break
        if looks_like_mover:
            catalyst_bonus += 0.6
        return catalyst_type, looks_like_mover, catalyst_bonus

    def _fetch_benzinga_events(self, tickers_csv: str | None) -> list[dict[str, Any]]:
        res = self.benzinga.fetch_events(page_size=100, tickers=tickers_csv)
        if not res.get("ok"):
            return []
        rows: list[dict[str, Any]] = []
        for item in res.get("events") or []:
            rows.append(
                {
                    "title": str(item.get("title") or ""),
                    "summary": "",
                    "channels": [str(ch) for ch in (item.get("channels") or [])],
                    "symbols": [str(t).upper() for t in (item.get("tickers") or []) if str(t).strip()],
                    "url": str(item.get("url") or "https://api.benzinga.com"),
                    "published_at": item.get("created") or item.get("updated"),
                    "updated_at": item.get("updated") or item.get("created"),
                    "source_name": "benzinga_newswire",
                }
            )
        return rows

    def _fetch_alpaca_news_events(self, tickers: list[str] | None) -> list[dict[str, Any]]:
        res = self.alpaca_news.fetch_events(symbols=tickers or None, limit=50)
        if not res.get("ok"):
            return []
        rows: list[dict[str, Any]] = []
        for item in res.get("events") or []:
            rows.append(
                {
                    "title": str(item.get("headline") or ""),
                    "summary": str(item.get("summary") or ""),
                    "channels": [str(item.get("source") or "alpaca_news")],
                    "symbols": [str(t).upper() for t in (item.get("symbols") or []) if str(t).strip()],
                    "url": str(item.get("url") or "https://data.alpaca.markets/v1beta1/news"),
                    "published_at": item.get("created_at") or item.get("updated_at"),
                    "updated_at": item.get("updated_at") or item.get("created_at"),
                    "source_name": "alpaca_news",
                }
            )
        return rows

    def collect(self, tickers: list[str] | None = None) -> list[dict[str, object]]:
        tickers_csv = self._normalized_tickers_csv(tickers)
        requested = {str(t).upper() for t in (tickers or []) if str(t).strip()}
        raw_items = [*self._fetch_benzinga_events(tickers_csv), *self._fetch_alpaca_news_events(sorted(requested) if requested else None)]
        if not raw_items and not requested:
            return []

        symbol_evidence: dict[str, list[dict[str, Any]]] = {}
        symbol_scores: dict[str, float] = {}
        symbol_mentions: dict[str, dict[str, int]] = {}
        for item in raw_items:
            catalyst_type, looks_like_mover, bonus = self._classify(item.get("title") or "", item.get("summary") or "", item.get("channels") or [])
            item["catalyst_type"] = catalyst_type
            item["looks_like_mover"] = looks_like_mover
            item_score = 1.0 + bonus
            for symbol in item.get("symbols") or []:
                symbol_evidence.setdefault(symbol, []).append(item)
                symbol_scores[symbol] = symbol_scores.get(symbol, 0.0) + item_score
                source_bucket = symbol_mentions.setdefault(symbol, {})
                source_name = str(item.get("source_name") or "unknown")
                source_bucket[source_name] = source_bucket.get(source_name, 0) + 1

        candidate_symbols = sorted(symbol_scores, key=lambda symbol: (symbol_scores[symbol], symbol), reverse=True)
        if requested:
            candidate_symbols = sorted(requested)
        candidate_symbols = candidate_symbols[:25]

        events: list[dict[str, object]] = []
        for symbol in candidate_symbols:
            evidence = symbol_evidence.get(symbol, [])
            top_item = sorted(evidence, key=lambda row: (1 if row.get("looks_like_mover") else 0, row.get("published_at") or ""), reverse=True)[0] if evidence else None
            overlay = build_overlay_for_symbol(symbol, md=self.md)
            gap_pct = overlay.gap_pct or 0.0
            premarket_dollar_volume = overlay.premarket_dollar_volume or 0.0
            spread_pct = overlay.estimated_spread_pct
            market_confirms = abs(gap_pct) >= 4.0 or premarket_dollar_volume >= 500_000 or (abs(gap_pct) >= 2.0 and premarket_dollar_volume >= 250_000)
            looks_like_mover = any(bool(row.get("looks_like_mover")) for row in evidence)
            if not requested and not looks_like_mover and not market_confirms:
                continue

            catalyst_type = str((top_item or {}).get("catalyst_type") or "exchange_mover")
            headline = str((top_item or {}).get("title") or f"{symbol} premarket mover candidate")
            summary = str((top_item or {}).get("summary") or "")
            url = str((top_item or {}).get("url") or f"https://finance.yahoo.com/quote/{symbol}")
            published_at = (top_item or {}).get("published_at")
            updated_at = (top_item or {}).get("updated_at")
            mentions = symbol_mentions.get(symbol, {})
            notes = [
                f"benzinga_hits={mentions.get('benzinga_newswire', 0)}",
                f"alpaca_news_hits={mentions.get('alpaca_news', 0)}",
                f"gap_pct={round(gap_pct, 4)}",
                f"premarket_dollar_volume={round(premarket_dollar_volume, 2)}",
                f"execution_readiness_score={overlay.execution_readiness_score}",
            ]
            if spread_pct is not None:
                notes.append(f"spread_pct={round(spread_pct, 4)}")
            notes.extend([f"blocker={reason}" for reason in (overlay.execution_blockers or [])[:3]])
            notes.extend([f"warning={reason}" for reason in (overlay.execution_warnings or [])[:3]])

            credibility = 5.8 + min(1.8, symbol_scores.get(symbol, 0.0) * 0.35) + (0.6 if market_confirms else 0.0)
            if looks_like_mover:
                credibility += 0.3
            event = raw_event(
                source_name="exchange_scout",
                source_tier=1,
                source_url=url,
                headline=f"{symbol} exchange mover candidate | {headline}",
                raw_text=" | ".join(part for part in [headline, summary, f"gap_pct={round(gap_pct, 4)}", f"premarket_dollar_volume={round(premarket_dollar_volume, 2)}"] if part),
                company_name=None,
                ticker_candidates=[symbol],
                catalyst_type=catalyst_type,
                official_flag=False,
                structured_flag=True,
                social_flag=False,
                credibility_score_initial=min(8.4, credibility),
                extraction_confidence=0.82 if looks_like_mover or market_confirms else 0.7,
                published_at=published_at,
                updated_at=updated_at,
                notes=notes,
            )
            events.append(event.to_dict())
        return events
