from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..common.config import load_env_file


@dataclass
class StreamStatus:
    trade_updates_connected: bool = False
    market_data_connected: bool = False
    last_error: str | None = None


class AlpacaStreamsAdapter:
    """Alpaca SIP/IEX quote and trade stream adapter.

    The adapter exposes the real alpaca-py ``StockDataStream`` subscription path
    and keeps a small in-memory/JSONL status surface for the deterministic
    opening-bell supervisor. Tests can still use the status holder without
    opening a network socket.
    """

    def __init__(self, *, output_dir: str | Path | None = None, feed: str | None = None) -> None:
        load_env_file()
        self.api_key = os.getenv("ALPACA_API_KEY_ID", "").strip()
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()
        self.feed = (feed or os.getenv("ALPACA_MARKET_DATA_FEED", "sip")).strip().lower() or "sip"
        self.output_dir = Path(output_dir) if output_dir else None
        self.status = StreamStatus()
        self._stream: Any | None = None

    def configured(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def _feed_enum(self) -> Any:
        from alpaca.data.enums import DataFeed

        return {"sip": DataFeed.SIP, "iex": DataFeed.IEX, "otc": DataFeed.OTC}.get(self.feed, DataFeed.SIP)

    def _build_stream(self) -> Any:
        if not self.configured():
            raise RuntimeError("alpaca_stream_credentials_missing")
        from alpaca.data.live import StockDataStream

        self._stream = StockDataStream(self.api_key, self.secret_key, raw_data=False, feed=self._feed_enum())
        return self._stream

    def _log_path(self, name: str) -> Path | None:
        if self.output_dir is None:
            return None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir / name

    def _append_jsonl(self, name: str, payload: dict[str, Any]) -> None:
        path = self._log_path(name)
        if path is None:
            return
        with path.open("a") as fh:
            fh.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

    @staticmethod
    def _obj_to_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            try:
                data = value.model_dump()
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        out: dict[str, Any] = {}
        for key in dir(value):
            if key.startswith("_"):
                continue
            try:
                item = getattr(value, key)
            except Exception:
                continue
            if not callable(item):
                out[key] = item
        return out

    def normalize_quote(self, event: Any) -> dict[str, Any]:
        row = self._obj_to_dict(event)
        return {
            "type": "quote",
            "symbol": row.get("symbol") or row.get("S"),
            "timestamp": row.get("timestamp") or row.get("t") or datetime.now(timezone.utc).isoformat(),
            "bid": row.get("bid_price") or row.get("bp"),
            "ask": row.get("ask_price") or row.get("ap"),
            "bid_size": row.get("bid_size") or row.get("bs"),
            "ask_size": row.get("ask_size") or row.get("as_") or row.get("as"),
            "feed": self.feed,
            "raw": row,
        }

    def normalize_trade(self, event: Any) -> dict[str, Any]:
        row = self._obj_to_dict(event)
        return {
            "type": "trade",
            "symbol": row.get("symbol") or row.get("S"),
            "timestamp": row.get("timestamp") or row.get("t") or datetime.now(timezone.utc).isoformat(),
            "price": row.get("price") or row.get("p"),
            "size": row.get("size") or row.get("s"),
            "feed": self.feed,
            "raw": row,
        }

    def subscribe_quotes_and_trades(self, symbols: list[str], *, quote_handler: Any | None = None, trade_handler: Any | None = None) -> Any:
        stream = self._stream or self._build_stream()
        normalized_symbols = sorted({str(symbol).upper().strip() for symbol in symbols if str(symbol).strip()})
        if not normalized_symbols:
            raise ValueError("alpaca_stream_symbols_missing")

        async def on_quote(event: Any) -> None:
            payload = self.normalize_quote(event)
            self.mark_market_data(True)
            self._append_jsonl("raw_quotes.jsonl", payload)
            if quote_handler:
                result = quote_handler(payload)
                if hasattr(result, "__await__"):
                    await result

        async def on_trade(event: Any) -> None:
            payload = self.normalize_trade(event)
            self.mark_market_data(True)
            self._append_jsonl("raw_trades.jsonl", payload)
            if trade_handler:
                result = trade_handler(payload)
                if hasattr(result, "__await__"):
                    await result

        stream.subscribe_quotes(on_quote, *normalized_symbols)
        stream.subscribe_trades(on_trade, *normalized_symbols)
        return stream

    def run(self) -> None:
        stream = self._stream or self._build_stream()
        stream.run()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()

    def mark_trade_updates(self, connected: bool, error: str | None = None) -> None:
        self.status.trade_updates_connected = connected
        self.status.last_error = error

    def mark_market_data(self, connected: bool, error: str | None = None) -> None:
        self.status.market_data_connected = connected
        self.status.last_error = error

    def snapshot(self) -> dict[str, Any]:
        return {
            "trade_updates_connected": self.status.trade_updates_connected,
            "market_data_connected": self.status.market_data_connected,
            "last_error": self.status.last_error,
        }
