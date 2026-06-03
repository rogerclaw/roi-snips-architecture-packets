"""Webull market-data adapter with SDK/HTTP integration paths."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any

from ..common.http_utils import http_get_json
from .webull_rest import WebullRESTClient


def _looks_like_subscription_error(error: str | None) -> bool:
    text = (error or "").lower()
    return "subscribe to stock quotes" in text or "insufficient permission" in text


@dataclass
class WebullMDConfig:
    app_key: str
    app_secret: str
    region: str = "US"
    base_url: str = "https://api.webull.com"


class WebullMarketDataAdapter:
    def __init__(self, cfg: WebullMDConfig | None = None) -> None:
        self.cfg = cfg or WebullMDConfig(
            app_key=os.getenv("WEBULL_APP_KEY", ""),
            app_secret=os.getenv("WEBULL_APP_SECRET", ""),
            region=(os.getenv("WEBULL_REGION_ID", "us")).upper(),
            base_url=os.getenv("WEBULL_HTTP_API_BASE", "https://api.webull.com"),
        )

    def _has_creds(self) -> bool:
        return bool(self.cfg.app_key and self.cfg.app_secret)

    def _sdk_healthcheck(self) -> dict[str, Any]:
        try:
            mod_client = importlib.import_module("webullsdkcore.client")
            mod_region = importlib.import_module("webullsdkcore.common.region")
            mod_trade_api = importlib.import_module("webullsdktrade.api")
        except Exception as e:
            return {"ok": False, "reason": "sdk_import_failed", "error": str(e)}

        try:
            region_map = {"US": mod_region.Region.US.value, "HK": mod_region.Region.HK.value, "JP": mod_region.Region.JP.value}
            api_client = mod_client.ApiClient(self.cfg.app_key, self.cfg.app_secret, region_map.get(self.cfg.region, mod_region.Region.US.value))
            api = mod_trade_api.API(api_client)
            if hasattr(api, "account") and hasattr(api.account, "get_app_subscriptions"):
                res = api.account.get_app_subscriptions()
                status = getattr(res, "status_code", None)
                return {"ok": bool(status == 200), "status": status, "mode": "sdk"}
            return {"ok": True, "mode": "sdk", "note": "sdk_loaded_no_account_probe"}
        except Exception as e:
            return {"ok": False, "reason": "sdk_probe_failed", "error": str(e)}

    def healthcheck(self, symbol: str = "SPY") -> dict[str, Any]:
        if not self._has_creds():
            return {"ok": False, "reason": "missing_webull_credentials"}

        sdk = self._sdk_healthcheck()
        if sdk.get("ok"):
            quote = self.get_quote(symbol)
            bars = self.get_bars_1m(symbol, limit=2)
            return {"ok": quote.get("ok") and bars.get("ok"), "mode": sdk.get("mode", "sdk"), "quote": quote, "bars": bars}

        rest = WebullRESTClient()
        rest_res = rest.stock_snapshot(symbol)
        if rest_res.ok:
            bars = self.get_bars_1m(symbol, limit=2)
            return {"ok": bars.get("ok"), "status": rest_res.status, "mode": "signed_http", "quote": self.get_quote(symbol), "bars": bars}
        if _looks_like_subscription_error(rest_res.error):
            return {
                "ok": False,
                "reason": "webull_market_data_subscription_required",
                "status": rest_res.status,
                "mode": "signed_http",
                "error": rest_res.error,
            }

        snapshot_url = os.getenv("WEBULL_MD_HTTP_URL")
        if snapshot_url:
            headers = {
                "X-APP-KEY": self.cfg.app_key,
                "X-APP-SECRET": self.cfg.app_secret,
                "Accept": "application/json",
            }
            res = http_get_json(snapshot_url, headers=headers, params={"symbol": symbol})
            return {"ok": res.ok, "status": res.status, "mode": "http", "error": res.error}

        return {
            "ok": False,
            "reason": "webull_market_data_not_configured",
            "sdk": sdk,
            "signed_http": {"status": rest_res.status, "error": rest_res.error},
        }

    def get_quote(self, symbol: str) -> dict[str, Any]:
        rest = WebullRESTClient()
        res = rest.stock_snapshot(symbol)
        if res.ok:
            payload = res.data[0] if isinstance(res.data, list) and res.data else (res.data or {})
            quote = payload if isinstance(payload, dict) else {}
            normalized = {
                **quote,
                "last": quote.get("last") or quote.get("lastPrice") or quote.get("price"),
                "prev_close": quote.get("prev_close") or quote.get("previousClose") or quote.get("pre_close"),
                "bid": quote.get("bid") or quote.get("bidPrice") or quote.get("bid_price"),
                "ask": quote.get("ask") or quote.get("askPrice") or quote.get("ask_price"),
                "halt_status": quote.get("halt_status") or quote.get("haltStatus") or "NONE",
            }
            return {"ok": True, "symbol": symbol, "quote": normalized}

        quote_url = os.getenv("WEBULL_MD_HTTP_URL")
        if not quote_url:
            reason = "webull_market_data_subscription_required" if _looks_like_subscription_error(res.error) else "missing_webull_md_http_url"
            return {"ok": False, "reason": reason, "symbol": symbol, "status": res.status, "error": res.error}
        headers = {
            "X-APP-KEY": self.cfg.app_key,
            "X-APP-SECRET": self.cfg.app_secret,
            "Accept": "application/json",
        }
        bearer = os.getenv("WEBULL_ACCESS_TOKEN")
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        res = http_get_json(quote_url, headers=headers, params={"symbol": symbol})
        if not res.ok:
            return {"ok": False, "reason": "webull_md_http_error", "status": res.status, "error": res.error}
        return {"ok": True, "symbol": symbol, "quote": res.data}

    def get_bars_1m(self, symbol: str, limit: int = 60) -> dict[str, Any]:
        rest = WebullRESTClient()
        res = rest.stock_bars(symbol, timespan="M1", count=limit)
        if res.ok:
            bars = res.data if isinstance(res.data, list) else (res.data.get("bars") if isinstance(res.data, dict) else res.data)
            return {"ok": True, "symbol": symbol, "bars": bars or []}

        bars_url = os.getenv("WEBULL_BARS_HTTP_URL")
        if not bars_url:
            reason = "webull_market_data_subscription_required" if _looks_like_subscription_error(res.error) else "missing_webull_bars_http_url"
            return {"ok": False, "reason": reason, "symbol": symbol, "status": res.status, "error": res.error}
        headers = {
            "X-APP-KEY": self.cfg.app_key,
            "X-APP-SECRET": self.cfg.app_secret,
            "Accept": "application/json",
        }
        bearer = os.getenv("WEBULL_ACCESS_TOKEN")
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        res = http_get_json(bars_url, headers=headers, params={"symbol": symbol, "interval": "1m", "limit": limit})
        if not res.ok:
            return {"ok": False, "reason": "webull_bars_http_error", "status": res.status, "error": res.error}
        bars = res.data if isinstance(res.data, list) else (res.data.get("bars") if isinstance(res.data, dict) else res.data)
        return {"ok": True, "symbol": symbol, "bars": bars or []}
