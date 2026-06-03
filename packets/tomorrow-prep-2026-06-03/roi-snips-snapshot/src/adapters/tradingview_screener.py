"""TradingView-style scanner adapter.

No credentials are faked. The adapter stays disabled unless explicitly enabled
with ROI_SNIPS_ENABLE_TRADINGVIEW_SCREENER=true because this endpoint is a
screening interface, not a broker/data entitlement.
"""

from __future__ import annotations

import os
from typing import Any

from ..common.http_utils import http_post_json


class TradingViewScreenerAdapter:
    def __init__(self, base_url: str = "https://scanner.tradingview.com") -> None:
        self.base_url = os.getenv("TRADINGVIEW_SCREENER_BASE_URL", base_url).rstrip("/")
        self.enabled = os.getenv("ROI_SNIPS_ENABLE_TRADINGVIEW_SCREENER", "false").strip().lower() in {"1", "true", "yes", "on"}

    def fetch_us_movers(self, *, limit: int = 50) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "reason": "tradingview_screener_disabled", "rows": []}
        payload = {
            "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}],
            "options": {"lang": "en"},
            "markets": ["america"],
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": ["name", "description", "close", "change", "volume", "relative_volume_10d_calc", "market_cap_basic"],
            "sort": {"sortBy": "relative_volume_10d_calc", "sortOrder": "desc"},
            "range": [0, max(1, int(limit))],
        }
        res = http_post_json(f"{self.base_url}/america/scan", payload)
        if not res.ok:
            return {"ok": False, "reason": "tradingview_screener_http_error", "status": res.status, "error": res.error, "rows": []}
        rows = []
        for item in (res.data or {}).get("data") or []:
            data = item.get("d") or []
            symbol = str(data[0] if data else "").upper().strip()
            if symbol:
                rows.append({"symbol": symbol, "description": data[1] if len(data) > 1 else None, "close": data[2] if len(data) > 2 else None, "change": data[3] if len(data) > 3 else None, "volume": data[4] if len(data) > 4 else None, "relative_volume": data[5] if len(data) > 5 else None, "market_cap": data[6] if len(data) > 6 else None})
        return {"ok": True, "rows": rows, "count": len(rows)}
