"""Webull trading adapter with deterministic preview/place/cancel/query hooks."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from ..common.http_utils import http_get_json, http_post_form_json
from .webull_rest import WebullRESTClient


@dataclass
class WebullTradeConfig:
    app_key: str
    app_secret: str
    account_id: str
    base_url: str = "https://api.webull.com"


class WebullTradeAdapter:
    def __init__(self, cfg: WebullTradeConfig | None = None) -> None:
        self.cfg = cfg or WebullTradeConfig(
            app_key=os.getenv("WEBULL_APP_KEY", ""),
            app_secret=os.getenv("WEBULL_APP_SECRET", ""),
            account_id=os.getenv("WEBULL_ACCOUNT_ID", ""),
            base_url=os.getenv("WEBULL_HTTP_API_BASE", "https://api.webull.com"),
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "X-APP-KEY": self.cfg.app_key,
            "X-APP-SECRET": self.cfg.app_secret,
            "Accept": "application/json",
        }
        bearer = os.getenv("WEBULL_ACCESS_TOKEN")
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        return headers

    def runtime_environment(self) -> dict[str, Any]:
        return {
            "provider": "webull",
            "environment": os.getenv("WEBULL_ENVIRONMENT", "live").strip().lower() or "live",
            "base_url": self.cfg.base_url,
            "configured": bool(self.cfg.app_key and self.cfg.app_secret),
        }

    def _post(self, env_name: str, form: dict[str, Any], missing_reason: str) -> dict[str, Any]:
        url = os.getenv(env_name)
        if not url:
            return {"ok": False, "reason": missing_reason, "request": form}
        payload = {"account_id": self.cfg.account_id, **form}
        res = http_post_form_json(url, form=payload, headers=self._headers())
        if not res.ok:
            return {"ok": False, "reason": env_name.lower() + "_error", "status": res.status, "error": res.error}
        return {"ok": True, "data": res.data}

    def _get(self, env_name: str, params: dict[str, Any], missing_reason: str) -> dict[str, Any]:
        url = os.getenv(env_name)
        if not url:
            return {"ok": False, "reason": missing_reason, "request": params}
        payload = {"account_id": self.cfg.account_id, **params}
        res = http_get_json(url, headers=self._headers(), params=payload)
        if not res.ok:
            return {"ok": False, "reason": env_name.lower() + "_error", "status": res.status, "error": res.error}
        return {"ok": True, "data": res.data}

    def healthcheck(self) -> dict[str, Any]:
        if not (self.cfg.app_key and self.cfg.app_secret):
            return {"ok": False, "reason": "missing_webull_trade_credentials"}
        rest = WebullRESTClient()
        accounts_res = rest.list_accounts()
        if not accounts_res.ok:
            if not self.cfg.account_id:
                return {"ok": False, "reason": "missing_webull_account_id", "status": accounts_res.status, "error": accounts_res.error}
            res = self.list_open_orders(limit=1)
            if res.get("ok"):
                return {"ok": True, "mode": "http"}
            return res

        accounts = accounts_res.data if isinstance(accounts_res.data, list) else accounts_res.data
        if not self.cfg.account_id:
            return {"ok": True, "mode": "signed_http", "account_id_configured": False, "accounts": accounts}

        balance_res = rest.account_balance(self.cfg.account_id)
        open_res = rest.open_orders(self.cfg.account_id, page_size=1)
        if balance_res.ok and open_res.ok:
            return {
                "ok": True,
                "mode": "signed_http",
                "account_id_configured": True,
                "cash_balance": (balance_res.data or {}).get("total_cash_balance") if isinstance(balance_res.data, dict) else None,
                "open_orders_count": len(open_res.data or []) if isinstance(open_res.data, list) else None,
            }
        return {
            "ok": False,
            "reason": "webull_trade_healthcheck_failed",
            "balance_status": balance_res.status,
            "balance_error": balance_res.error,
            "open_orders_status": open_res.status,
            "open_orders_error": open_res.error,
        }

    def preview_order(self, order: dict[str, Any]) -> dict[str, Any]:
        res = self._post("WEBULL_TRADE_PREVIEW_URL", {"order": str(order)}, "missing_webull_trade_preview_url")
        if not res.get("ok"):
            return res
        return {"ok": True, "preview": res["data"]}

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        res = self._post("WEBULL_TRADE_PLACE_URL", {"order": str(order)}, "missing_webull_trade_place_url")
        if not res.get("ok"):
            return res
        return {"ok": True, "placement": res["data"]}

    def cancel_order(self, broker_order_id: str) -> dict[str, Any]:
        res = self._post(
            "WEBULL_TRADE_CANCEL_URL",
            {"broker_order_id": broker_order_id},
            "missing_webull_trade_cancel_url",
        )
        if not res.get("ok"):
            return res
        return {"ok": True, "cancel": res["data"]}

    def query_order(self, broker_order_id: str) -> dict[str, Any]:
        rest = WebullRESTClient()
        if self.cfg.account_id:
            res = rest.order_detail(self.cfg.account_id, broker_order_id)
            if res.ok:
                return {"ok": True, "order": res.data}
        res = self._get(
            "WEBULL_TRADE_QUERY_URL",
            {"broker_order_id": broker_order_id},
            "missing_webull_trade_query_url",
        )
        if not res.get("ok"):
            return res
        return {"ok": True, "order": res["data"]}

    def replace_order(self, broker_order_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        del broker_order_id, fields
        return {"ok": False, "reason": "webull_replace_not_supported"}

    def list_accounts(self) -> dict[str, Any]:
        rest = WebullRESTClient()
        res = rest.list_accounts()
        if not res.ok:
            return {"ok": False, "reason": "webull_account_list_error", "status": res.status, "error": res.error}
        data = res.data if isinstance(res.data, list) else (res.data.get("accounts") if isinstance(res.data, dict) else res.data)
        return {"ok": True, "accounts": data or []}

    def get_balance(self) -> dict[str, Any]:
        rest = WebullRESTClient()
        if self.cfg.account_id:
            res = rest.account_balance(self.cfg.account_id)
            if res.ok:
                return {"ok": True, "balance": res.data}
            return {"ok": False, "reason": "webull_balance_error", "status": res.status, "error": res.error}
        return {"ok": False, "reason": "missing_webull_account_id"}

    def get_account(self) -> dict[str, Any]:
        balance = self.get_balance()
        if not balance.get("ok"):
            return balance
        raw = balance.get("balance") or {}
        if not isinstance(raw, dict):
            return {"ok": False, "reason": "webull_balance_malformed", "balance": raw}
        cash = raw.get("cash") or raw.get("total_cash_balance") or raw.get("available_cash_balance")
        buying_power = raw.get("buying_power") or raw.get("total_buying_power") or raw.get("available_buying_power") or cash
        return {
            "ok": True,
            "account": {
                "cash": cash,
                "buying_power": buying_power,
                "non_marginable_buying_power": raw.get("non_marginable_buying_power") or buying_power,
                "regt_buying_power": raw.get("regt_buying_power") or buying_power,
                "raw": raw,
            },
        }

    def list_open_orders(self, limit: int = 50) -> dict[str, Any]:
        rest = WebullRESTClient()
        if self.cfg.account_id:
            res = rest.open_orders(self.cfg.account_id, page_size=limit)
            if res.ok:
                data = res.data
                orders = data if isinstance(data, list) else (data.get("orders") if isinstance(data, dict) else data)
                return {"ok": True, "orders": orders or []}
        res = self._get(
            "WEBULL_TRADE_OPEN_ORDERS_URL",
            {"limit": limit},
            "missing_webull_trade_open_orders_url",
        )
        if not res.get("ok"):
            return res
        data = res["data"]
        orders = data if isinstance(data, list) else (data.get("orders") if isinstance(data, dict) else data)
        return {"ok": True, "orders": orders or []}

    def list_positions(self) -> dict[str, Any]:
        rest = WebullRESTClient()
        if self.cfg.account_id:
            res = rest.account_positions(self.cfg.account_id)
            if res.ok:
                data = res.data
                positions = data if isinstance(data, list) else (data.get("positions") if isinstance(data, dict) else data)
                return {"ok": True, "positions": positions or []}
        res = self._get("WEBULL_TRADE_POSITIONS_URL", {}, "missing_webull_trade_positions_url")
        if not res.get("ok"):
            return res
        data = res["data"]
        positions = data if isinstance(data, list) else (data.get("positions") if isinstance(data, dict) else data)
        return {"ok": True, "positions": positions or []}
