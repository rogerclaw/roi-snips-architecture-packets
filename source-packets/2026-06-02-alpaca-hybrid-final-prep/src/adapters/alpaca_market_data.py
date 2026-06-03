from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from ..common.config import load_env_file


def _obj_to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    data = {}
    for key in dir(value):
        if key.startswith("_"):
            continue
        try:
            item = getattr(value, key)
        except Exception:
            continue
        if callable(item):
            continue
        data[key] = item
    return data


def _unwrap_symbol_mapping(value: Any, symbol: str) -> Any:
    if isinstance(value, dict):
        if symbol in value:
            return value[symbol]
        if symbol.upper() in value:
            return value[symbol.upper()]
        if len(value) == 1:
            return next(iter(value.values()))
    return value


def _truthy_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_sip_recent_entitlement_error(reason: str | None) -> bool:
    text = str(reason or "").lower()
    return "sip" in text and "subscription" in text and "permit" in text


class AlpacaMarketDataAdapter:
    def __init__(self) -> None:
        load_env_file()
        self.api_key = os.getenv("ALPACA_API_KEY_ID", "").strip()
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()
        self.feed = os.getenv("ALPACA_MARKET_DATA_FEED", "sip").strip().lower() or "sip"
        self.allow_iex_fallback = _truthy_env("ALPACA_ALLOW_IEX_FALLBACK", default=True)

    def configured(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def runtime_environment(self) -> dict[str, Any]:
        return {
            "provider": "alpaca_market_data",
            "feed": self.feed,
            "allow_iex_fallback": self.allow_iex_fallback,
            "configured": self.configured(),
            "data_base_url": os.getenv("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets").strip(),
        }

    def _client(self):
        if not self.configured():
            raise RuntimeError("alpaca_credentials_missing")
        from alpaca.data.historical.stock import StockHistoricalDataClient

        return StockHistoricalDataClient(self.api_key, self.secret_key)

    def _feed(self, feed_name: str | None = None):
        from alpaca.data.enums import DataFeed

        resolved = (feed_name or self.feed).strip().lower()
        mapping = {
            "sip": DataFeed.SIP,
            "iex": DataFeed.IEX,
            "otc": DataFeed.OTC,
        }
        return mapping.get(resolved, DataFeed.SIP)

    def _normalize_quote(self, quote: Any, trade: Any | None = None) -> dict[str, Any]:
        q = _obj_to_dict(quote)
        t = _obj_to_dict(trade)
        bid = q.get("bid_price") or q.get("bp")
        ask = q.get("ask_price") or q.get("ap")
        last = t.get("price") or t.get("p")
        spread_bps = None
        try:
            if bid is not None and ask is not None and last not in (None, 0, "0"):
                spread_bps = ((float(ask) - float(bid)) / float(last)) * 10000.0
        except Exception:
            spread_bps = None
        return {
            "bid": bid,
            "ask": ask,
            "bid_size": q.get("bid_size") or q.get("bs"),
            "ask_size": q.get("ask_size") or q.get("as_") or q.get("as"),
            "last": last,
            "timestamp": q.get("timestamp") or q.get("t") or t.get("timestamp") or t.get("t"),
            "spread_bps": round(spread_bps, 4) if spread_bps is not None else None,
            "raw_quote": q,
            "raw_trade": t,
        }

    def _normalize_bar(self, bar: Any) -> dict[str, Any]:
        row = _obj_to_dict(bar)
        return {
            "timestamp": row.get("timestamp") or row.get("t"),
            "open": row.get("open") or row.get("o"),
            "high": row.get("high") or row.get("h"),
            "low": row.get("low") or row.get("l"),
            "close": row.get("close") or row.get("c"),
            "volume": row.get("volume") or row.get("v"),
            "trade_count": row.get("trade_count") or row.get("n"),
            "vwap": row.get("vwap") or row.get("vw"),
            "raw": row,
        }

    def _quote_for_feed(self, symbol: str, feed_name: str) -> dict[str, Any]:
        try:
            from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest

            client = self._client()
            quote_req = StockLatestQuoteRequest(symbol_or_symbols=[symbol], feed=self._feed(feed_name))
            trade_req = StockLatestTradeRequest(symbol_or_symbols=[symbol], feed=self._feed(feed_name))
            quote = _unwrap_symbol_mapping(client.get_stock_latest_quote(quote_req), symbol)
            trade = _unwrap_symbol_mapping(client.get_stock_latest_trade(trade_req), symbol)
            return {"ok": True, "quote": self._normalize_quote(quote, trade=trade), "feed": feed_name}
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_quote_unavailable:{exc}", "feed": feed_name}

    def get_quote(self, symbol: str) -> dict[str, Any]:
        primary = self._quote_for_feed(symbol, self.feed)
        if primary.get("ok"):
            return primary
        if self.feed == "sip" and self.allow_iex_fallback and _is_sip_recent_entitlement_error(str(primary.get("reason") or "")):
            fallback = self._quote_for_feed(symbol, "iex")
            if fallback.get("ok"):
                quote = dict(fallback.get("quote") or {})
                quote["requested_feed"] = "sip"
                quote["fallback_from_feed"] = "sip"
                quote["fallback_reason"] = primary.get("reason")
                quote["data_scope_note"] = "IEX fallback used because SIP recent quote entitlement is unavailable; do not treat as full SIP execution data."
                fallback["quote"] = quote
                fallback["requested_feed"] = "sip"
                fallback["fallback_from_feed"] = "sip"
                fallback["fallback_reason"] = primary.get("reason")
                return fallback
            primary["fallback_attempted_feed"] = "iex"
            primary["fallback_reason"] = fallback.get("reason")
        return primary

    def get_bars_1m(self, symbol: str, limit: int = 120) -> dict[str, Any]:
        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            client = self._client()
            requested_limit = max(1, int(limit))
            start = datetime.now(timezone.utc) - timedelta(minutes=max(requested_limit * 4, 30))
            req = StockBarsRequest(symbol_or_symbols=[symbol], timeframe=TimeFrame.Minute, start=start, end=datetime.now(timezone.utc), feed=self._feed())
            bars = client.get_stock_bars(req)
            if hasattr(bars, "data"):
                bars = getattr(bars, "data")
            bars = _unwrap_symbol_mapping(bars, symbol)
            if not isinstance(bars, list):
                bars = list(bars or [])
            return {"ok": True, "bars": [self._normalize_bar(bar) for bar in bars][-requested_limit:], "feed": self.feed}
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_bars_unavailable:{exc}", "feed": self.feed}

    def get_bars_1d(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            client = self._client()
            start = datetime.now(timezone.utc) - timedelta(days=max(int(limit) * 3, 30))
            req = StockBarsRequest(symbol_or_symbols=[symbol], timeframe=TimeFrame.Day, start=start, limit=max(1, int(limit)), feed=self._feed())
            bars = client.get_stock_bars(req)
            if hasattr(bars, "data"):
                bars = getattr(bars, "data")
            bars = _unwrap_symbol_mapping(bars, symbol)
            if not isinstance(bars, list):
                bars = list(bars or [])
            return {"ok": True, "bars": [self._normalize_bar(bar) for bar in bars], "feed": self.feed}
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_daily_bars_unavailable:{exc}", "feed": self.feed}

    def get_snapshot(self, symbol: str) -> dict[str, Any]:
        quote = self.get_quote(symbol)
        bars = self.get_bars_1m(symbol, limit=5)
        if not quote.get("ok") or not bars.get("ok"):
            return {"ok": False, "reason": quote.get("reason") or bars.get("reason")}
        latest_bar = (bars.get("bars") or [])[-1] if (bars.get("bars") or []) else None
        return {"ok": True, "snapshot": {"symbol": symbol, "quote": quote.get("quote"), "latest_bar": latest_bar, "feed": self.feed}}

    def healthcheck(self, symbol: str = "SPY") -> dict[str, Any]:
        quote = self.get_quote(symbol)
        bars = self.get_bars_1m(symbol, limit=2)
        daily = self.get_bars_1d(symbol, limit=2)
        if quote.get("ok") and daily.get("ok"):
            daily_bars = daily.get("bars") or []
            if daily_bars:
                prior_close = daily_bars[-2].get("close") if len(daily_bars) >= 2 else daily_bars[-1].get("close")
                if prior_close is not None:
                    quote_payload = dict(quote.get("quote") or {})
                    quote_payload["prev_close"] = prior_close
                    quote["quote"] = quote_payload
        return {"ok": quote.get("ok") and bars.get("ok"), "quote": quote, "bars": bars, "feed": quote.get("feed") or self.feed, "requested_feed": self.feed}
