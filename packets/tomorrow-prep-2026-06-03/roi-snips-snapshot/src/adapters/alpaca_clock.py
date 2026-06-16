from __future__ import annotations

from typing import Any

from .alpaca_trade import AlpacaTradeAdapter


class AlpacaClockAdapter:
    def __init__(self, trade_adapter: AlpacaTradeAdapter | None = None) -> None:
        self.trade_adapter = trade_adapter or AlpacaTradeAdapter()

    def get_clock(self) -> dict[str, Any]:
        try:
            clock = self.trade_adapter._client().get_clock()
            if hasattr(clock, "model_dump"):
                data = clock.model_dump()
            elif isinstance(clock, dict):
                data = clock
            else:
                data = {k: getattr(clock, k) for k in dir(clock) if not k.startswith("_") and not callable(getattr(clock, k))}
            return {"ok": True, "clock": data}
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_clock_unavailable:{exc}"}
