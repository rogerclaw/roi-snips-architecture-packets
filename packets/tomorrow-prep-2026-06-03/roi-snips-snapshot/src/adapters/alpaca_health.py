from __future__ import annotations

from typing import Any

from .alpaca_clock import AlpacaClockAdapter
from .alpaca_market_data import AlpacaMarketDataAdapter
from .alpaca_trade import AlpacaTradeAdapter


class AlpacaHealthAdapter:
    def __init__(
        self,
        trade_adapter: AlpacaTradeAdapter | None = None,
        market_data_adapter: AlpacaMarketDataAdapter | None = None,
        clock_adapter: AlpacaClockAdapter | None = None,
    ) -> None:
        self.trade_adapter = trade_adapter or AlpacaTradeAdapter()
        self.market_data_adapter = market_data_adapter or AlpacaMarketDataAdapter()
        self.clock_adapter = clock_adapter or AlpacaClockAdapter(self.trade_adapter)

    def healthcheck(self, symbol: str = "SPY") -> dict[str, Any]:
        account = self.trade_adapter.get_account()
        orders = self.trade_adapter.list_open_orders(limit=5)
        quote = self.market_data_adapter.get_quote(symbol)
        bars = self.market_data_adapter.get_bars_1m(symbol, limit=2)
        clock = self.clock_adapter.get_clock()
        return {
            "ok": all([account.get("ok"), orders.get("ok"), quote.get("ok"), bars.get("ok"), clock.get("ok")]),
            "account": account,
            "open_orders": orders,
            "quote": quote,
            "bars": bars,
            "clock": clock,
            "feed": self.market_data_adapter.feed,
        }
