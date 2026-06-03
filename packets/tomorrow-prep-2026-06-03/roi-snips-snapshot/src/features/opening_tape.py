"""First-seconds opening tape feature extraction.

This module is intentionally deterministic and side-effect free. Live stream
supervisors can feed quote/trade events into ``OpeningTapeTracker``; tests and
readiness checks can feed synthetic events with the same shape.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


WINDOW_SECONDS = (5, 10, 15, 30, 60)


def _ts(value: Any, default: datetime | None = None) -> datetime:
    if value is None:
        return default or datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        raw = float(value)
        if raw > 10_000_000_000:
            raw /= 1000.0
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _f(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


@dataclass
class QuoteTick:
    timestamp: datetime
    bid: float | None
    ask: float | None
    bid_size: float | None = None
    ask_size: float | None = None


@dataclass
class TradeTick:
    timestamp: datetime
    price: float
    size: float


@dataclass
class OpeningTapeTracker:
    symbol: str
    premarket_high: float | None = None
    premarket_vwap: float | None = None
    thesis_break: float | None = None
    expected_opening_dollar_volume_60s: float | None = None
    premarket_dollar_volume_per_minute: float | None = None
    quotes: list[QuoteTick] = field(default_factory=list)
    trades: list[TradeTick] = field(default_factory=list)
    opening_trade: TradeTick | None = None
    opening_window_trades: list[TradeTick] = field(default_factory=list)
    regular_open_time: datetime | None = None

    def update_quote(self, event: dict[str, Any]) -> None:
        self.quotes.append(
            QuoteTick(
                timestamp=_ts(event.get("timestamp") or event.get("ts")),
                bid=_f(event.get("bid") or event.get("bid_price") or event.get("bp")),
                ask=_f(event.get("ask") or event.get("ask_price") or event.get("ap")),
                bid_size=_f(event.get("bid_size") or event.get("bs")),
                ask_size=_f(event.get("ask_size") or event.get("as") or event.get("as_")),
            )
        )
        self.quotes = self.quotes[-500:]

    def update_trade(self, event: dict[str, Any]) -> None:
        price = _f(event.get("price") or event.get("p") or event.get("last"))
        size = _f(event.get("size") or event.get("s") or event.get("volume"), 0.0)
        if price is None:
            return
        trade = TradeTick(timestamp=_ts(event.get("timestamp") or event.get("ts")), price=price, size=float(size or 0.0))
        if self.opening_trade is None:
            self.opening_trade = trade
        self.trades.append(trade)
        self.trades = self.trades[-2000:]
        if self.regular_open_time is None:
            self.regular_open_time = trade.timestamp.replace(hour=13, minute=30, second=0, microsecond=0)
        if trade.timestamp <= self.opening_trade.timestamp + timedelta(seconds=max(WINDOW_SECONDS)):
            self.opening_window_trades.append(trade)

    @property
    def latest_quote(self) -> QuoteTick | None:
        return self.quotes[-1] if self.quotes else None

    @property
    def latest_trade(self) -> TradeTick | None:
        return self.trades[-1] if self.trades else None

    @property
    def first_trade(self) -> TradeTick | None:
        return self.opening_trade or (self.trades[0] if self.trades else None)

    def _window_trades(self, seconds: int) -> list[TradeTick]:
        if not self.first_trade:
            return []
        start = self.first_trade.timestamp
        end = start + timedelta(seconds=seconds)
        rows_by_key: dict[tuple[datetime, float, float], TradeTick] = {}
        for tick in [*self.opening_window_trades, *self.trades]:
            if start <= tick.timestamp <= end:
                rows_by_key[(tick.timestamp, tick.price, tick.size)] = tick
        return sorted(rows_by_key.values(), key=lambda tick: tick.timestamp)

    def _window_features(self, seconds: int) -> dict[str, float | None]:
        rows = self._window_trades(seconds)
        if not rows:
            return {
                f"open_{seconds}s": None,
                f"high_{seconds}s": None,
                f"low_{seconds}s": None,
                f"close_{seconds}s": None,
                f"window_volume_{seconds}s": 0.0,
                f"window_dollar_volume_{seconds}s": 0.0,
                f"window_vwap_{seconds}s": None,
                f"trade_count_{seconds}s": 0.0,
            }
        prices = [row.price for row in rows]
        volume = sum(max(row.size, 0.0) for row in rows)
        dollar_volume = sum(row.price * max(row.size, 0.0) for row in rows)
        return {
            f"open_{seconds}s": prices[0],
            f"high_{seconds}s": max(prices),
            f"low_{seconds}s": min(prices),
            f"close_{seconds}s": prices[-1],
            f"window_volume_{seconds}s": volume,
            f"window_dollar_volume_{seconds}s": dollar_volume,
            f"window_vwap_{seconds}s": (dollar_volume / volume) if volume else prices[-1],
            f"trade_count_{seconds}s": float(len(rows)),
        }

    def features(self, as_of: datetime | None = None) -> dict[str, Any]:
        now = _ts(as_of)
        quote = self.latest_quote
        trade = self.latest_trade
        first = self.first_trade
        bid = quote.bid if quote else None
        ask = quote.ask if quote else None
        valid_quote = (
            bid is not None
            and ask is not None
            and math.isfinite(float(bid))
            and math.isfinite(float(ask))
            and bid > 0
            and ask > bid
        )
        mid = ((bid + ask) / 2.0) if valid_quote else None
        spread_cents = (ask - bid) if valid_quote else None
        spread_bps = ((spread_cents / mid) * 10000.0) if spread_cents is not None and mid else None
        quote_age_ms = (now - quote.timestamp).total_seconds() * 1000.0 if quote else None
        trade_age_ms = (now - trade.timestamp).total_seconds() * 1000.0 if trade else None

        out: dict[str, Any] = {
            "symbol": self.symbol,
            "latest_quote_timestamp": quote.timestamp.isoformat() if quote else None,
            "latest_trade_timestamp": trade.timestamp.isoformat() if trade else None,
            "bid": bid,
            "ask": ask,
            "bid_size": quote.bid_size if quote else None,
            "ask_size": quote.ask_size if quote else None,
            "spread_cents": round(spread_cents, 4) if spread_cents is not None else None,
            "spread_bps": round(spread_bps, 4) if spread_bps is not None else None,
            "quote_age_ms": round(quote_age_ms, 2) if quote_age_ms is not None else None,
            "trade_age_ms": round(trade_age_ms, 2) if trade_age_ms is not None else None,
            "first_trade_price": first.price if first else None,
            "regular_open_price": first.price if first else None,
            "latest_price": trade.price if trade else None,
        }
        for seconds in WINDOW_SECONDS:
            out.update(self._window_features(seconds))

        latest = _f(out.get("latest_price"))
        open_price = _f(out.get("regular_open_price"))
        premarket_high = _f(self.premarket_high)
        micro_vwap_10 = _f(out.get("window_vwap_10s"))
        dollar_60 = float(out.get("window_dollar_volume_60s") or 0.0)
        expected = self.expected_opening_dollar_volume_60s or self.premarket_dollar_volume_per_minute or 0.0
        opening_vs_premarket_rate_score = _clamp((dollar_60 / expected) * 10.0 if expected > 0 else 0.0)
        absolute_dollar_volume_score = _clamp(dollar_60 / 150_000.0)
        trade_count_velocity_score = _clamp(float(out.get("trade_count_60s") or 0.0) / 12.0)
        dollar_30 = float(out.get("window_dollar_volume_30s") or 0.0)
        dollar_10 = float(out.get("window_dollar_volume_10s") or 0.0)
        dollar_5 = float(out.get("window_dollar_volume_5s") or 0.0)
        dollar_15 = float(out.get("window_dollar_volume_15s") or 0.0)
        relative_to_prior_minutes_score = _clamp((dollar_30 / max(dollar_10 * 3.0, 1.0)) * 5.0 if dollar_10 > 0 else 0.0)
        acceleration_vs_previous_window_score = _clamp((max(dollar_15 - dollar_5, 0.0) / max(dollar_5, 1.0)) * 4.0 if dollar_5 > 0 else 0.0)
        continuation_volume_expansion_score = _clamp((max(dollar_60 - (dollar_30 * 2.0), 0.0) / max(dollar_30, 1.0)) * 5.0 if dollar_30 > 0 else 0.0)
        volume_quality_after_reset_score = _clamp(max(absolute_dollar_volume_score, opening_vs_premarket_rate_score) * 0.65 + continuation_volume_expansion_score * 0.35)
        bid_volume_support_score = bid_refresh_score(self.quotes)
        volume_burst_ratio = max(
            opening_vs_premarket_rate_score,
            absolute_dollar_volume_score,
            trade_count_velocity_score,
            relative_to_prior_minutes_score,
            acceleration_vs_previous_window_score,
            continuation_volume_expansion_score,
            volume_quality_after_reset_score,
            bid_volume_support_score * 0.7,
        )

        out["price_above_open"] = bool(latest is not None and open_price is not None and latest > open_price)
        out["price_above_premarket_high"] = bool(latest is not None and premarket_high is not None and latest > premarket_high)
        out["premarket_high_break_confirmed"] = bool(out["price_above_premarket_high"] and _f(out.get("low_10s"), latest) >= premarket_high * 0.995 if latest is not None and premarket_high else False)
        out["premarket_high_reclaim_confirmed"] = bool(latest is not None and premarket_high is not None and _f(out.get("low_30s"), latest) < premarket_high <= latest)
        out["micro_vwap_hold"] = bool(latest is not None and micro_vwap_10 is not None and latest >= micro_vwap_10)
        out["absolute_dollar_volume_score"] = round(absolute_dollar_volume_score, 4)
        out["absolute_dollar_volume_60s"] = round(dollar_60, 2)
        out["relative_to_prior_minutes_score"] = round(relative_to_prior_minutes_score, 4)
        out["opening_vs_premarket_rate_score"] = round(opening_vs_premarket_rate_score, 4)
        out["acceleration_vs_previous_window_score"] = round(acceleration_vs_previous_window_score, 4)
        out["continuation_volume_expansion_score"] = round(continuation_volume_expansion_score, 4)
        out["volume_quality_after_reset_score"] = round(volume_quality_after_reset_score, 4)
        out["trade_count_velocity_score"] = round(trade_count_velocity_score, 4)
        out["bid_volume_support_score"] = round(bid_volume_support_score, 4)
        out["volume_burst_ratio"] = round(volume_burst_ratio, 4)
        out["volume_burst_components"] = {
            "absolute_dollar_volume": round(absolute_dollar_volume_score, 4),
            "relative_to_last_premarket_minutes": round(opening_vs_premarket_rate_score, 4),
            "relative_to_opening_expectation": round(opening_vs_premarket_rate_score, 4),
            "acceleration_vs_previous_window": round(acceleration_vs_previous_window_score, 4),
            "continuation_volume_expansion": round(continuation_volume_expansion_score, 4),
            "volume_quality_after_reset": round(volume_quality_after_reset_score, 4),
        }
        out["spread_regime"] = spread_regime(spread_bps)
        out["bid_refresh_score"] = round(bid_volume_support_score, 3)
        out["bid_collapse_flag"] = bid_collapse_flag(self.quotes)
        out["ask_lift_score"] = round(ask_lift_score(self.trades, ask), 3)
        out["upper_wick_fade_score"] = round(upper_wick_fade_score(out), 3)
        out["rug_pull_score"] = round(rug_pull_score(out), 3)
        out["chase_risk_score"] = round(chase_risk_score(out, premarket_high), 3)
        out["spread_explosion_flag"] = bool(spread_bps is not None and spread_bps >= 250.0)
        out["ask_wall_flag"] = bool(quote and quote.ask_size and quote.bid_size and quote.ask_size >= quote.bid_size * 8)
        out["opening_drive_score"] = round(opening_drive_score(out), 3)
        out["data_health_score"] = round(data_health_score(out), 3)
        out["open_execution_confidence"] = round(min(out["data_health_score"], out["opening_drive_score"]), 3)
        out["tape_state"] = tape_state(out)
        return out


def spread_regime(spread_bps: float | None) -> str:
    if spread_bps is None:
        return "MECHANICALLY_IMPOSSIBLE"
    if not math.isfinite(float(spread_bps)) or spread_bps <= 0:
        return "MECHANICALLY_IMPOSSIBLE"
    if spread_bps <= 50:
        return "TIGHT"
    if spread_bps <= 100:
        return "OK"
    if spread_bps <= 200:
        return "WIDE"
    if spread_bps <= 250:
        return "DANGEROUS"
    return "MECHANICALLY_IMPOSSIBLE"


def bid_refresh_score(quotes: list[QuoteTick]) -> float:
    if len(quotes) < 3:
        return 0.0
    recent = quotes[-8:]
    sizes = [float(q.bid_size or 0.0) for q in recent]
    bids = [float(q.bid or 0.0) for q in recent]
    positive = sum(1 for value in sizes if value > 0)
    stable = sum(1 for prev, cur in zip(bids, bids[1:]) if cur >= prev * 0.995 and cur > 0)
    return _clamp((positive / len(sizes)) * 5.0 + (stable / max(1, len(bids) - 1)) * 5.0)


def bid_collapse_flag(quotes: list[QuoteTick]) -> bool:
    if len(quotes) < 2:
        return False
    prev, cur = quotes[-2], quotes[-1]
    if prev.bid and cur.bid and cur.bid < prev.bid * 0.985:
        return True
    if prev.bid_size and cur.bid_size is not None and cur.bid_size < prev.bid_size * 0.25:
        return True
    if prev.bid and prev.ask and cur.bid and cur.ask:
        prev_spread = prev.ask - prev.bid
        cur_spread = cur.ask - cur.bid
        return prev_spread > 0 and cur_spread > prev_spread * 3.0
    return False


def ask_lift_score(trades: list[TradeTick], ask: float | None) -> float:
    if not trades or ask is None:
        return 0.0
    recent = trades[-20:]
    lifts = sum(1 for tick in recent if tick.price >= ask * 0.999)
    volume = sum(max(tick.size, 0.0) for tick in recent)
    return _clamp((lifts / len(recent)) * 7.0 + min(3.0, volume / 50_000.0))


def upper_wick_fade_score(features: dict[str, Any]) -> float:
    high = _f(features.get("high_30s"))
    low = _f(features.get("low_30s"))
    close = _f(features.get("close_30s"))
    if high is None or low is None or close is None or high <= low:
        return 0.0
    return _clamp(((high - close) / (high - low)) * 10.0)


def rug_pull_score(features: dict[str, Any]) -> float:
    open_price = _f(features.get("regular_open_price"))
    low = _f(features.get("low_30s"))
    close = _f(features.get("close_30s"))
    if open_price is None or low is None or close is None or open_price <= 0:
        return 0.0
    dump_pct = max((open_price - min(low, close)) / open_price * 100.0, 0.0)
    return _clamp(dump_pct * 3.0 + (4.0 if close < open_price else 0.0))


def chase_risk_score(features: dict[str, Any], reference: float | None) -> float:
    latest = _f(features.get("latest_price"))
    if latest is None or not reference:
        return 0.0
    return _clamp(max((latest / reference - 1.0) * 100.0, 0.0) * 1.4)


def data_health_score(features: dict[str, Any]) -> float:
    if features.get("bid") is None or features.get("ask") is None:
        return 0.0
    quote_age_ms = features.get("quote_age_ms")
    if (999999 if quote_age_ms is None else float(quote_age_ms)) > 1000:
        return 2.0
    if features.get("spread_regime") == "MECHANICALLY_IMPOSSIBLE":
        return 0.0
    if features.get("spread_regime") == "DANGEROUS":
        return 5.0
    if features.get("spread_regime") == "WIDE":
        return 7.0
    return 10.0


def opening_drive_score(features: dict[str, Any]) -> float:
    volume_burst_score = _clamp(float(features.get("volume_burst_ratio") or 0.0))
    price_above_open_score = 10.0 if features.get("price_above_open") else 0.0
    premkt_score = 10.0 if features.get("premarket_high_break_confirmed") or features.get("premarket_high_reclaim_confirmed") else 0.0
    micro_vwap_score = 10.0 if features.get("micro_vwap_hold") else 0.0
    spread_score = {"TIGHT": 10.0, "OK": 8.0, "WIDE": 5.0, "DANGEROUS": 2.0, "MECHANICALLY_IMPOSSIBLE": 0.0}.get(str(features.get("spread_regime")), 0.0)
    score = (
        0.22 * volume_burst_score
        + 0.18 * float(features.get("ask_lift_score") or 0.0)
        + 0.15 * float(features.get("bid_refresh_score") or 0.0)
        + 0.15 * price_above_open_score
        + 0.12 * premkt_score
        + 0.10 * micro_vwap_score
        + 0.08 * spread_score
        - 0.15 * float(features.get("upper_wick_fade_score") or 0.0)
        - 0.15 * float(features.get("rug_pull_score") or 0.0)
        - 0.10 * float(features.get("chase_risk_score") or 0.0)
    )
    return _clamp(score)


def tape_state(features: dict[str, Any]) -> str:
    if features.get("bid") is None or features.get("ask") is None:
        return "HALT_OR_NO_QUOTE"
    quote_age_ms = features.get("quote_age_ms")
    if (999999 if quote_age_ms is None else float(quote_age_ms)) > 1000:
        return "STALE_DATA"
    if features.get("spread_regime") == "MECHANICALLY_IMPOSSIBLE":
        return "SPREAD_EXPLODED"
    if not features.get("first_trade_price"):
        return "FIRST_PRINT_WAIT"
    if features.get("rug_pull_score", 0) >= 7:
        return "GAP_AND_CRAP"
    if features.get("bid_collapse_flag"):
        return "DRIVE_FAILED"
    if features.get("opening_drive_score", 0) >= 7.8:
        return "DRIVE_CONFIRMED"
    if features.get("opening_drive_score", 0) >= 6.5:
        return "DRIVE_CONFIRMING"
    return "FIRST_PRINT_SEEN"
