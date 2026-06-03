from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..common.config import load_live_config
from ..common.provider_factory import build_trade_adapter
from .audit_logger import append_audit_event


class PositionManager:
    def __init__(self, trade_adapter: Any | None = None, cfg: dict[str, Any] | None = None) -> None:
        self.cfg = cfg or load_live_config()
        self.trade_adapter = trade_adapter or build_trade_adapter(self.cfg)

    def count_open_positions(self) -> dict[str, Any]:
        res = self.trade_adapter.list_positions()
        if not res.get("ok"):
            return res
        positions = res.get("positions") or []
        positive = []
        for row in positions:
            qty = row.get("quantity") or row.get("qty") or row.get("position") or 0
            try:
                if float(qty) > 0:
                    positive.append(row)
            except Exception:
                continue
        return {"ok": True, "count": len(positive), "positions": positive}

    def cancel_all_open_orders(self) -> dict[str, Any]:
        orders_res = self.trade_adapter.list_open_orders()
        if not orders_res.get("ok"):
            append_audit_event("cancel_all_failed", {"reason": orders_res.get("reason")}, status="error")
            return orders_res

        cancelled = []
        failures = []
        for order in orders_res.get("orders") or []:
            broker_order_id = order.get("broker_order_id") or order.get("orderId") or order.get("id")
            if not broker_order_id:
                continue
            append_audit_event("pre_cancel", {"broker_order_id": broker_order_id, "order": order})
            res = self.trade_adapter.cancel_order(str(broker_order_id))
            append_audit_event("post_cancel", {"broker_order_id": broker_order_id, "response": res}, status="ok" if res.get("ok") else "error")
            if res.get("ok"):
                cancelled.append(broker_order_id)
            else:
                failures.append({"broker_order_id": broker_order_id, "reason": res.get("reason")})
        return {"ok": not failures, "cancelled": cancelled, "failures": failures}

    def flatten_all_positions(self, live_enabled: bool = False) -> dict[str, Any]:
        positions_res = self.trade_adapter.list_positions()
        if not positions_res.get("ok"):
            append_audit_event("flatten_all_failed", {"reason": positions_res.get("reason")}, status="error")
            return positions_res

        exit_orders = []
        failures = []
        for row in positions_res.get("positions") or []:
            symbol = row.get("symbol") or row.get("ticker")
            qty = row.get("quantity") or row.get("qty") or row.get("position") or 0
            try:
                qty_f = float(qty)
            except Exception:
                qty_f = 0.0
            if not symbol or qty_f <= 0:
                continue
            order = {
                "symbol": symbol,
                "side": "SELL",
                "order_type": "MARKET",
                "quantity": int(qty_f),
                "time_in_force": "DAY",
                "client_order_id": f"flat_{symbol}_{int(datetime.now(timezone.utc).timestamp())}",
            }
            append_audit_event("pre_flatten_preview", {"symbol": symbol, "order": order})
            preview = self.trade_adapter.preview_order(order)
            append_audit_event("post_flatten_preview", {"symbol": symbol, "response": preview}, status="ok" if preview.get("ok") else "error")
            if not preview.get("ok"):
                failures.append({"symbol": symbol, "stage": "preview", "reason": preview.get("reason")})
                continue
            if not live_enabled:
                exit_orders.append({"symbol": symbol, "order": order, "mode": "dry_run"})
                continue
            append_audit_event("pre_flatten_place", {"symbol": symbol, "order": order})
            placed = self.trade_adapter.place_order(order)
            append_audit_event("post_flatten_place", {"symbol": symbol, "response": placed}, status="ok" if placed.get("ok") else "error")
            if placed.get("ok"):
                exit_orders.append({"symbol": symbol, "order": order, "placement": placed})
            else:
                failures.append({"symbol": symbol, "stage": "place", "reason": placed.get("reason")})
        return {"ok": not failures, "flatten_orders": exit_orders, "failures": failures}
