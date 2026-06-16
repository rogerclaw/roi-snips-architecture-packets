from __future__ import annotations

from ...adapters.grok_search import GrokSearchAdapter
from ...adapters.reddit_feed import RedditFeedAdapter
from ...adapters.x_optional import XOptionalAdapter
from .common import raw_event


class SocialScout:
    def __init__(
        self,
        reddit: RedditFeedAdapter | None = None,
        x_adapter: XOptionalAdapter | None = None,
        grok: GrokSearchAdapter | None = None,
    ) -> None:
        self.reddit = reddit or RedditFeedAdapter()
        self.x_adapter = x_adapter or XOptionalAdapter()
        self.grok = grok or GrokSearchAdapter()

    def collect(self, tickers: list[str] | None = None) -> list[dict[str, object]]:
        filter_symbols = {str(t).upper() for t in (tickers or []) if str(t).strip()}
        out: list[dict[str, object]] = []

        reddit_res = self.reddit.fetch_themes()
        reddit_counts: dict[str, int] = {}
        if reddit_res.get("ok"):
            reddit_counts = {str(row["ticker"]).upper(): int(row["mentions"]) for row in (reddit_res.get("trending") or []) if isinstance(row, dict) and row.get("ticker")}
            for ticker, mentions in reddit_counts.items():
                if filter_symbols and ticker not in filter_symbols:
                    continue
                if mentions <= 0:
                    continue
                event = raw_event(
                    source_name="reddit",
                    source_tier=2,
                    source_url=f"https://reddit.com/search/?q=%24{ticker}",
                    headline=f"Reddit attention for {ticker}",
                    raw_text=f"{mentions} reddit mentions detected",
                    company_name=ticker,
                    ticker_candidates=[ticker],
                    catalyst_type="social_acceleration",
                    official_flag=False,
                    structured_flag=False,
                    social_flag=True,
                    credibility_score_initial=min(4.5, 1.0 + mentions * 0.2),
                    extraction_confidence=0.7,
                    notes=[f"mentions={mentions}", "source=reddit"],
                )
                out.append(event.to_dict())

        query_symbols = sorted(filter_symbols)[:8] if filter_symbols else sorted(reddit_counts)[:8]
        if query_symbols:
            x_query = "(" + " OR ".join(f"${ticker}" for ticker in query_symbols) + ") lang:en"
            x_res = self.x_adapter.fetch_recent(query=x_query, max_results=25)
            if x_res.get("ok"):
                counts = {ticker: 0 for ticker in query_symbols}
                for tweet in x_res.get("tweets") or []:
                    text = str(tweet.get("text") or "").upper()
                    for ticker in counts:
                        if f"${ticker}" in text or ticker in text.split():
                            counts[ticker] += 1
                for ticker, count in counts.items():
                    if count <= 0:
                        continue
                    event = raw_event(
                        source_name="x_optional",
                        source_tier=2,
                        source_url=f"https://x.com/search?q=%24{ticker}",
                        headline=f"X attention for {ticker}",
                        raw_text=f"{count} recent X mentions detected",
                        company_name=ticker,
                        ticker_candidates=[ticker],
                        catalyst_type="social_acceleration",
                        official_flag=False,
                        structured_flag=False,
                        social_flag=True,
                        credibility_score_initial=min(4.5, 1.0 + count * 0.15),
                        extraction_confidence=0.65,
                        notes=[f"mentions={count}", "source=x"],
                    )
                    out.append(event.to_dict())

        grok_symbols = sorted(filter_symbols)[:12] if filter_symbols else []
        grok_res = self.grok.fetch_x_candidates(tickers=grok_symbols)
        if grok_res.get("ok"):
            for row in grok_res.get("candidates") or []:
                ticker = str(row.get("ticker") or "").upper()
                if not ticker:
                    continue
                if filter_symbols and ticker not in filter_symbols:
                    continue
                mentions = int(row.get("mentions") or 0)
                if mentions <= 0:
                    continue
                urls = [str(url) for url in (row.get("evidence_urls") or []) if str(url).strip()]
                source_url = urls[0] if urls else f"https://x.com/search?q=%24{ticker}"
                snippets = [str(s) for s in (row.get("snippets") or []) if str(s).strip()]
                notes = [
                    f"mentions={mentions}",
                    "source=grok_x_search",
                    "auth_mode=openclaw_grok_web_search",
                ]
                notes.extend([f"citation={url}" for url in urls[:5]])
                event = raw_event(
                    source_name="grok_x_search",
                    source_tier=2,
                    source_url=source_url,
                    headline=f"Grok/X attention for {ticker}",
                    raw_text=(snippets[0] if snippets else f"{mentions} Grok/X ticker mentions detected"),
                    company_name=ticker,
                    ticker_candidates=[ticker],
                    catalyst_type="social_acceleration",
                    official_flag=False,
                    structured_flag=False,
                    social_flag=True,
                    credibility_score_initial=min(4.8, 1.2 + mentions * 0.15 + min(len(urls), 4) * 0.2),
                    extraction_confidence=0.68 if urls else 0.55,
                    notes=notes,
                )
                out.append(event.to_dict())

        return out
