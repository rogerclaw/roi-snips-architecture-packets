from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
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


class AlpacaTradeAdapter:
    def __init__(self) -> None:
        load_env_file()
        self.api_key = os.getenv("ALPACA_API_KEY_ID", "").strip()
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()
        self.base_url = os.getenv("ALPACA_BASE_URL", "https://api.alpaca.markets").strip()
        self.paper = os.getenv("ALPACA_PAPER", "false").strip().lower() in {"1", "true", "yes", "on"}

    def configured(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def runtime_environment(self) -> dict[str, Any]:
        environment = "paper" if self.paper else "live"
        return {
            "provider": "alpaca",
            "environment": environment,
            "paper": self.paper,
            "base_url": self.base_url,
            "configured": self.configured(),
        }

    def _client(self):
        if not self.configured():
            raise RuntimeError("alpaca_credentials_missing")
        from alpaca.trading.client import TradingClient

        kwargs: dict[str, Any] = {"paper": self.paper}
        if self.base_url:
            kwargs["url_override"] = self.base_url
        return TradingClient(self.api_key, self.secret_key, **kwargs)

    def _time_in_force(self, value: str):
        from alpaca.trading.enums import TimeInForce

        mapping = {
            "DAY": TimeInForce.DAY,
            "GTC": TimeInForce.GTC,
            "OPG": TimeInForce.OPG,
        }
        return mapping.get(str(value or "DAY").upper(), TimeInForce.DAY)

    def _side(self, value: str):
        from alpaca.trading.enums import OrderSide

        return OrderSide.BUY if str(value or "BUY").upper() == "BUY" else OrderSide.SELL

    def _order_class(self, value: str | None):
        if not value:
            return None
        from alpaca.trading.enums import OrderClass

        mapping = {
            "BRACKET": OrderClass.BRACKET,
            "OCO": OrderClass.OCO,
            "OTO": OrderClass.OTO,
        }
        return mapping.get(str(value).upper())

    def deterministic_client_order_id(self, order: dict[str, Any]) -> str:
        raw = "|".join(
            [
                str(order.get("account_id") or "default"),
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                str(order.get("symbol") or ""),
                str(order.get("mode") or order.get("strategy") or ""),
                str(order.get("trigger") or ""),
                str(order.get("setup_bucket") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M")),
                str(order.get("side") or "BUY"),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _normalize_order(self, order: Any) -> dict[str, Any]:
        row = _obj_to_dict(order)
        return {
            "broker_order_id": row.get("id") or row.get("order_id"),
            "client_order_id": row.get("client_order_id"),
            "symbol": row.get("symbol"),
            "side": str(row.get("side") or ""),
            "status": str(row.get("status") or ""),
            "qty": row.get("qty") or row.get("filled_qty") or row.get("notional"),
            "notional": row.get("notional"),
            "limit_price": row.get("limit_price"),
            "stop_price": row.get("stop_price"),
            "filled_avg_price": row.get("filled_avg_price"),
            "order_class": str(row.get("order_class") or ""),
            "time_in_force": str(row.get("time_in_force") or ""),
            "extended_hours": bool(row.get("extended_hours") or False),
            "raw": row,
        }

    def _normalize_position(self, position: Any) -> dict[str, Any]:
        row = _obj_to_dict(position)
        return {
            "symbol": row.get("symbol"),
            "qty": row.get("qty") or row.get("quantity") or "0",
            "market_value": row.get("market_value"),
            "avg_entry_price": row.get("avg_entry_price"),
            "side": row.get("side") or "long",
            "unrealized_pl": row.get("unrealized_pl"),
            "unrealized_plpc": row.get("unrealized_plpc"),
            "raw": row,
        }

    def get_account(self) -> dict[str, Any]:
        try:
            account = self._client().get_account()
            row = _obj_to_dict(account)
            return {
                "ok": True,
                "account": {
                    "account_number": row.get("account_number"),
                    "buying_power": row.get("buying_power"),
                    "non_marginable_buying_power": row.get("non_marginable_buying_power"),
                    "equity": row.get("equity"),
                    "cash": row.get("cash"),
                    "daytrade_count": row.get("daytrade_count"),
                    "pattern_day_trader": row.get("pattern_day_trader"),
                    "trading_blocked": row.get("trading_blocked"),
                    "account_blocked": row.get("account_blocked"),
                    "multiplier": row.get("multiplier"),
                    "raw": row,
                },
            }
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_account_unavailable:{exc}"}

    def get_asset(self, symbol: str) -> dict[str, Any]:
        try:
            asset = self._client().get_asset(symbol)
            row = _obj_to_dict(asset)
            vetoes = []
            status_raw = str(row.get("status") or "unknown")
            status_normalized = status_raw.split(".")[-1].lower()
            if status_normalized != "active":
                vetoes.append("asset_not_active")
            if not bool(row.get("tradable", False)):
                vetoes.append("asset_not_tradable")
            return {
                "ok": True,
                "asset": {
                    "symbol": row.get("symbol") or symbol,
                    "asset_class": str(row.get("asset_class") or "us_equity"),
                    "exchange": row.get("exchange"),
                    "status": status_raw,
                    "tradable": bool(row.get("tradable", False)),
                    "fractionable": bool(row.get("fractionable", False)),
                    "fractional_eh_enabled": bool(row.get("fractionable", False)),
                    "ipo": row.get("ipo"),
                    "route_allowed": not vetoes,
                    "veto_reasons": vetoes,
                    "raw": row,
                },
            }
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_asset_unavailable:{exc}"}

    def list_positions(self) -> dict[str, Any]:
        try:
            positions = self._client().get_all_positions()
            return {"ok": True, "positions": [self._normalize_position(p) for p in positions]}
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_positions_unavailable:{exc}"}

    def list_open_orders(self, limit: int = 50) -> dict[str, Any]:
        try:
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest

            req = GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=max(1, min(int(limit), 500)))
            orders = self._client().get_orders(filter=req)
            return {"ok": True, "orders": [self._normalize_order(o) for o in orders]}
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_open_orders_unavailable:{exc}"}

    def query_order(self, broker_order_id: str) -> dict[str, Any]:
        client = self._client()
        try:
            order = client.get_order_by_id(broker_order_id)
            return {"ok": True, "order": self._normalize_order(order)}
        except Exception:
            try:
                order = client.get_order_by_client_id(broker_order_id)
                return {"ok": True, "order": self._normalize_order(order)}
            except Exception as exc:
                return {"ok": False, "reason": f"alpaca_order_unavailable:{exc}"}

    def _has_duplicate_order(self, client_order_id: str, symbol: str | None = None) -> tuple[bool, str | None]:
        open_orders = self.list_open_orders()
        if not open_orders.get("ok"):
            return True, open_orders.get("reason")
        for order in open_orders.get("orders") or []:
            if client_order_id and order.get("client_order_id") == client_order_id:
                return True, "duplicate_client_order_id"
            if symbol and order.get("symbol") == symbol and str(order.get("status") or "").lower() in {"new", "accepted", "partially_filled", "pending_new", "pending_replace", "pending_cancel"}:
                return True, "duplicate_symbol_order"
        return False, None

    def preview_order(self, order: dict[str, Any]) -> dict[str, Any]:
        client_order_id = str(order.get("client_order_id") or self.deterministic_client_order_id(order))
        duplicate, reason = self._has_duplicate_order(client_order_id, symbol=order.get("symbol"))
        if duplicate:
            return {"ok": False, "reason": reason or "duplicate_order_risk"}
        asset = self.get_asset(str(order.get("symbol") or ""))
        if not asset.get("ok"):
            return asset
        vetoes = list(((asset.get("asset") or {}).get("veto_reasons") or []))
        if vetoes:
            return {"ok": False, "reason": ",".join(vetoes), "asset": asset.get("asset")}
        if bool(order.get("extended_hours")) and str(order.get("order_type") or "LIMIT").upper() == "MARKET":
            return {"ok": False, "reason": "extended_hours_market_order_not_allowed"}
        return {"ok": True, "mode": "preview", "order": {**order, "client_order_id": client_order_id}, "asset": asset.get("asset")}

    def _build_order_request(self, order: dict[str, Any]):
        from alpaca.trading.enums import OrderClass
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, StopLossRequest, TakeProfitRequest

        side = self._side(str(order.get("side") or "BUY"))
        tif = self._time_in_force(str(order.get("time_in_force") or "DAY"))
        order_type = str(order.get("order_type") or "LIMIT").upper()
        order_class = self._order_class(order.get("order_class"))
        client_order_id = str(order.get("client_order_id") or self.deterministic_client_order_id(order))

        kwargs: dict[str, Any] = {
            "symbol": str(order["symbol"]),
            "side": side,
            "time_in_force": tif,
            "client_order_id": client_order_id,
        }
        if order.get("quantity") is not None:
            kwargs["qty"] = str(order.get("quantity"))
        elif order.get("qty") is not None:
            kwargs["qty"] = str(order.get("qty"))
        elif order.get("notional") is not None:
            kwargs["notional"] = str(order.get("notional"))
        elif order.get("notional_usd") is not None:
            kwargs["notional"] = str(order.get("notional_usd"))

        if order_class:
            kwargs["order_class"] = order_class
        if order.get("extended_hours") is not None:
            kwargs["extended_hours"] = bool(order.get("extended_hours"))
        if order_class == OrderClass.BRACKET:
            if order.get("target_1") is not None:
                kwargs["take_profit"] = TakeProfitRequest(limit_price=str(order.get("target_1")))
            if order.get("stop_price") is not None or order.get("initial_stop") is not None:
                kwargs["stop_loss"] = StopLossRequest(
                    stop_price=str(order.get("stop_price") or order.get("initial_stop")),
                    limit_price=str(order.get("stop_limit_price") or order.get("stop_price") or order.get("initial_stop")),
                )

        if order_type in {"MARKET"} and not order_class and not order.get("limit_price"):
            return MarketOrderRequest(**kwargs)

        kwargs["limit_price"] = str(order.get("limit_price") or order.get("entry_limit_price") or order.get("hard_max_entry_price"))
        return LimitOrderRequest(**kwargs)

    def place_order(self, order: dict[str, Any]) -> dict[str, Any]:
        preview = self.preview_order(order)
        if not preview.get("ok"):
            return preview
        try:
            request = self._build_order_request(preview.get("order") or order)
            placed = self._client().submit_order(order_data=request)
            return {"ok": True, "order": self._normalize_order(placed), "broker_order_id": getattr(placed, "id", None) or _obj_to_dict(placed).get("id")}
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_place_failed:{exc}"}

    def replace_order(self, broker_order_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        try:
            from alpaca.trading.requests import ReplaceOrderRequest

            payload: dict[str, Any] = {}
            if fields.get("quantity") is not None:
                payload["qty"] = str(fields.get("quantity"))
            if fields.get("limit_price") is not None:
                payload["limit_price"] = str(fields.get("limit_price"))
            if fields.get("time_in_force") is not None:
                payload["time_in_force"] = self._time_in_force(str(fields.get("time_in_force")))
            order = self._client().replace_order_by_id(broker_order_id, order_data=ReplaceOrderRequest(**payload))
            return {"ok": True, "order": self._normalize_order(order)}
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_replace_failed:{exc}"}

    def cancel_order(self, broker_order_id: str) -> dict[str, Any]:
        try:
            self._client().cancel_order_by_id(broker_order_id)
            return {"ok": True, "broker_order_id": broker_order_id}
        except Exception as exc:
            return {"ok": False, "reason": f"alpaca_cancel_failed:{exc}"}

    def healthcheck(self) -> dict[str, Any]:
        if not self.configured():
            return {"ok": False, "reason": "missing_alpaca_trade_credentials"}
        account = self.get_account()
        orders = self.list_open_orders(limit=5)
        reason = None
        if not account.get("ok"):
            reason = account.get("reason") or "alpaca_account_unavailable"
        elif not orders.get("ok"):
            reason = orders.get("reason") or "alpaca_open_orders_unavailable"
        return {
            "ok": account.get("ok") and orders.get("ok"),
            "reason": reason,
            "account": account,
            "open_orders": orders,
        }
