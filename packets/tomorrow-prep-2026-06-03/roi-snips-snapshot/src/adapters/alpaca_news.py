from __future__ import annotations

import os
from typing import Any

import requests

from ..common.config import load_env_file


class AlpacaNewsAdapter:
    def __init__(self) -> None:
        load_env_file()
        self.api_key = os.getenv("ALPACA_API_KEY_ID", "").strip()
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()
        self.data_base = os.getenv("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets").strip()

    def configured(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def fetch_events(self, symbols: list[str] | None = None, limit: int = 50) -> dict[str, Any]:
        if not self.configured():
            return {"ok": False, "reason": "alpaca_credentials_missing"}
        params: dict[str, Any] = {"limit": max(1, min(int(limit), 50))}
        if symbols:
            params["symbols"] = ",".join(sorted({s.upper() for s in symbols if s}))
        try:
            res = requests.get(
                f"{self.data_base}/v1beta1/news",
                params=params,
                headers={"APCA-API-KEY-ID": self.api_key, "APCA-API-SECRET-KEY": self.secret_key},
                timeout=20,
            )
            res.raise_for_status()
            rows = (res.json() or {}).get("news") or []
            events = []
            for row in rows:
                events.append(
                    {
                        "raw_id": row.get("id"),
                        "headline": row.get("headline"),
                        "summary": row.get("summary"),
                        "source": row.get("source"),
                        "created_at": row.get("created_at"),
                        "updated_at": row.get("updated_at"),
                        "url": row.get("url"),
                        "symbols": row.get("symbols") or [],
                        "raw": row,
                    }
                )
            return {"ok": True, "count": len(events), "events": events}
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_news_unavailable:{exc}"}
