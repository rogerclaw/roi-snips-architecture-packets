"""Financial Modeling Prep market movers adapter."""

from __future__ import annotations

import os
from typing import Any

from ..common.http_utils import http_get_json


class FmpMarketDataAdapter:
    def __init__(self, api_key: str | None = None, base_url: str = "https://financialmodelingprep.com/api/v3") -> None:
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        self.base_url = os.getenv("FMP_BASE_URL", base_url).rstrip("/")

    def configured(self) -> bool:
        return bool(self.api_key)

    def fetch_movers(self, *, lists: list[str] | None = None) -> dict[str, Any]:
        if not self.configured():
            return {"ok": False, "reason": "missing_fmp_api_key", "events": []}
        lists = lists or ["stock_market/gainers", "stock_market/actives"]
        rows: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for endpoint in lists:
            res = http_get_json(f"{self.base_url}/{endpoint}", params={"apikey": self.api_key})
            if not res.ok:
                errors.append({"endpoint": endpoint, "status": res.status, "error": res.error})
                continue
            payload = res.data if isinstance(res.data, list) else []
            for item in payload:
                symbol = str(item.get("symbol") or item.get("ticker") or "").upper().strip()
                if not symbol:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "name": item.get("name"),
                        "price": item.get("price"),
                        "change_percent": item.get("changesPercentage") or item.get("changePercent"),
                        "volume": item.get("volume"),
                        "source_endpoint": endpoint,
                    }
                )
        return {"ok": bool(rows), "reason": None if rows else "fmp_no_rows", "events": rows, "errors": errors}
