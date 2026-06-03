from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ...adapters.alpaca_news import AlpacaNewsAdapter
from ...adapters.benzinga_news import BenzingaNewsAdapter
from .common import raw_event


class KeywordNewsScoutBase:
    scout_name = "keyword_news_scout"
    catalyst_type = "structured_news"
    keywords: tuple[str, ...] = ()
    credibility_base = 6.4
    source_tier = 1
    max_freshness_hours = 120.0

    def __init__(
        self,
        benzinga: BenzingaNewsAdapter | None = None,
        alpaca_news: AlpacaNewsAdapter | None = None,
    ) -> None:
        self.benzinga = benzinga or BenzingaNewsAdapter()
        self.alpaca_news = alpaca_news or AlpacaNewsAdapter()
        self._keyword_patterns = [self._compile_keyword_pattern(keyword) for keyword in self.keywords]

    def _normalized_tickers(self, tickers: list[str] | None) -> list[str]:
        return sorted({str(t).upper() for t in (tickers or []) if str(t).strip()})

    def _compile_keyword_pattern(self, keyword: str) -> re.Pattern[str]:
        escaped = re.escape(keyword.lower())
        if re.search(r"[a-z0-9] [a-z0-9]", keyword.lower()):
            return re.compile(escaped, re.IGNORECASE)
        return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)

    def _match_keywords(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self._keyword_patterns)

    def _match_row(self, row: dict[str, Any]) -> bool:
        text = " ".join(
            [
                str(row.get("title") or ""),
                str(row.get("summary") or ""),
                " ".join(str(ch) for ch in (row.get("channels") or [])),
                str(row.get("source") or ""),
            ]
        )
        return self._match_keywords(text.lower())

    def _parse_ts(self, value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None

    def _freshness_hours(self, row: dict[str, Any]) -> float | None:
        ts = self._parse_ts(row.get("published_at") or row.get("updated_at"))
        if not ts:
            return None
        return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0)

    def _fresh_enough(self, row: dict[str, Any]) -> bool:
        freshness_hours = self._freshness_hours(row)
        if freshness_hours is None:
            return True
        return freshness_hours <= float(self.max_freshness_hours)

    def _fetch_benzinga(self, tickers: list[str]) -> list[dict[str, Any]]:
        tickers_csv = ",".join(tickers) if tickers else None
        res = self.benzinga.fetch_events(page_size=100, tickers=tickers_csv)
        if not res.get("ok"):
            return []
        rows: list[dict[str, Any]] = []
        for item in res.get("events") or []:
            row = {
                "title": str(item.get("title") or ""),
                "summary": "",
                "channels": [str(ch) for ch in (item.get("channels") or [])],
                "source": "benzinga_newswire",
                "symbols": [str(t).upper() for t in (item.get("tickers") or []) if str(t).strip()],
                "url": str(item.get("url") or "https://api.benzinga.com"),
                "published_at": item.get("created") or item.get("updated"),
                "updated_at": item.get("updated") or item.get("created"),
            }
            if row["symbols"] and self._match_row(row) and self._fresh_enough(row):
                rows.append(row)
        return rows

    def _fetch_alpaca(self, tickers: list[str]) -> list[dict[str, Any]]:
        res = self.alpaca_news.fetch_events(symbols=tickers or None, limit=50)
        if not res.get("ok"):
            return []
        rows: list[dict[str, Any]] = []
        for item in res.get("events") or []:
            row = {
                "title": str(item.get("headline") or ""),
                "summary": str(item.get("summary") or ""),
                "channels": [str(item.get("source") or "alpaca_news")],
                "source": str(item.get("source") or "alpaca_news"),
                "symbols": [str(t).upper() for t in (item.get("symbols") or []) if str(t).strip()],
                "url": str(item.get("url") or "https://data.alpaca.markets/v1beta1/news"),
                "published_at": item.get("created_at") or item.get("updated_at"),
                "updated_at": item.get("updated_at") or item.get("created_at"),
            }
            if row["symbols"] and self._match_row(row) and self._fresh_enough(row):
                rows.append(row)
        return rows

    def _event_notes(self, row: dict[str, Any], symbol: str) -> list[str]:
        notes = [f"source={row.get('source')}", f"scout={self.scout_name}"]
        freshness_hours = self._freshness_hours(row)
        if freshness_hours is not None:
            notes.append(f"freshness_hours={round(freshness_hours, 3)}")
        return notes

    def _event_for_row(self, row: dict[str, Any], symbol: str) -> dict[str, Any]:
        title = str(row.get("title") or "")
        summary = str(row.get("summary") or "")
        credibility = self.credibility_base + (0.4 if summary else 0.0)
        event = raw_event(
            source_name=self.scout_name,
            source_tier=self.source_tier,
            source_url=str(row.get("url") or "https://example.com"),
            headline=title or f"{symbol} structured catalyst candidate",
            raw_text=" | ".join(part for part in [title, summary] if part),
            company_name=None,
            ticker_candidates=[symbol],
            catalyst_type=self.catalyst_type,
            official_flag=False,
            structured_flag=True,
            social_flag=False,
            credibility_score_initial=min(8.5, credibility),
            extraction_confidence=0.8,
            published_at=row.get("published_at"),
            updated_at=row.get("updated_at"),
            notes=self._event_notes(row, symbol),
        )
        return event.to_dict()

    def collect(self, tickers: list[str] | None = None) -> list[dict[str, Any]]:
        normalized = self._normalized_tickers(tickers)
        rows = [*self._fetch_benzinga(normalized), *self._fetch_alpaca(normalized)]
        if not rows:
            return []
        events: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        requested = set(normalized)
        for row in rows:
            for symbol in row.get("symbols") or []:
                if requested and symbol not in requested:
                    continue
                key = (symbol, str(row.get("url") or row.get("title") or ""))
                if key in seen:
                    continue
                seen.add(key)
                events.append(self._event_for_row(row, symbol))
        return events
