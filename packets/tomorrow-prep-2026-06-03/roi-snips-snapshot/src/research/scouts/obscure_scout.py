from __future__ import annotations

from ...adapters.benzinga_news import BenzingaNewsAdapter
from ...adapters.reddit_feed import RedditFeedAdapter
from ...common.provider_factory import build_market_data_adapter
from .common import raw_event


MEGACAP_EXCLUSIONS = {"AAPL", "AMZN", "AMD", "GOOG", "GOOGL", "META", "MSFT", "NFLX", "NVDA", "PLTR", "SMCI", "SPY", "QQQ", "TSLA"}


class ObscureScout:
    def __init__(
        self,
        news: BenzingaNewsAdapter | None = None,
        reddit: RedditFeedAdapter | None = None,
        md: object | None = None,
    ) -> None:
        self.news = news or BenzingaNewsAdapter()
        self.reddit = reddit or RedditFeedAdapter()
        self.md = md or build_market_data_adapter()

    def _price_hint(self, symbol: str) -> float | None:
        res = self.md.get_quote(symbol)
        if not res.get("ok"):
            return None
        quote = res.get("quote") or {}
        try:
            return float(quote.get("last") or quote.get("last_price") or quote.get("price"))
        except Exception:
            return None

    def collect(self, tickers: list[str] | None = None) -> list[dict[str, object]]:
        requested = {str(t).upper() for t in (tickers or []) if str(t).strip()}
        reddit_res = self.reddit.fetch_themes()
        reddit_mentions = {str(row.get("ticker")).upper(): int(row.get("mentions") or 0) for row in (reddit_res.get("trending") or []) if isinstance(row, dict) and row.get("ticker")}
        news_res = self.news.fetch_events(page_size=100, tickers=",".join(sorted(requested)) if requested else None)
        if not news_res.get("ok"):
            return []

        emitted: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in news_res.get("events") or []:
            title = str(item.get("title") or "")
            lowered = title.lower()
            symbols = [str(t).upper() for t in (item.get("tickers") or []) if str(t).strip()]
            if not symbols:
                continue
            for symbol in symbols:
                if symbol in seen or symbol in MEGACAP_EXCLUSIONS:
                    continue
                if requested and symbol not in requested:
                    continue
                if len(symbol) > 5:
                    continue
                price = self._price_hint(symbol)
                mentions = int(reddit_mentions.get(symbol, 0))
                if price is not None and not (2.0 <= price <= 40.0):
                    continue
                if not any(k in lowered for k in ["approval", "contract", "launch", "partnership", "earnings", "guidance", "surges", "spikes", "acquire", "merger", "award", "trial"]) and mentions < 2:
                    continue
                credibility = 6.2 + min(1.4, mentions * 0.15)
                notes = ["lesser_known_candidate", f"mentions={mentions}"]
                if price is not None:
                    notes.append(f"price={round(price, 3)}")
                event = raw_event(
                    source_name="obscure_scout",
                    source_tier=1,
                    source_url=str(item.get("url") or "https://api.benzinga.com"),
                    headline=f"Obscure catalyst candidate: {symbol} | {title}",
                    raw_text=title,
                    company_name=None,
                    ticker_candidates=[symbol],
                    catalyst_type="obscure_catalyst_candidate",
                    official_flag=False,
                    structured_flag=False,
                    social_flag=False,
                    credibility_score_initial=min(8.0, credibility),
                    extraction_confidence=0.78,
                    published_at=item.get("created") or item.get("updated"),
                    updated_at=item.get("updated") or item.get("created"),
                    notes=notes,
                )
                emitted.append(event.to_dict())
                seen.add(symbol)
        return emitted
