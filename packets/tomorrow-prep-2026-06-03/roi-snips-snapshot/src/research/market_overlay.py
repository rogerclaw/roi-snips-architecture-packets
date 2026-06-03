from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from ..common.config import load_live_config
from ..common.provider_factory import build_market_data_adapter
from . import lifecycle as lc
from .models import MarketOverlay


def _bar_timestamp(bar: dict[str, Any]) -> datetime | None:
    raw = bar.get("timestamp") or bar.get("ts") or bar.get("time") or bar.get("datetime")
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)):
            value = float(raw)
            if value > 10_000_000_000:
                value /= 1000.0
            return datetime.fromtimestamp(value, tz=timezone.utc)
        text = str(raw).replace("Z", "+00:00")
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except Exception:
        return None


def _f(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _extract_quote_value(quote: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _f(quote.get(key))
        if value is not None:
            return value
    return None


def _extract_spread_pct(quote: dict[str, Any]) -> float | None:
    spread_bps = _extract_quote_value(quote, "spread_bps", "spreadBps")
    if spread_bps is not None:
        return spread_bps / 100.0
    bid = _extract_quote_value(quote, "bid", "bid_price", "bidPrice")
    ask = _extract_quote_value(quote, "ask", "ask_price", "askPrice")
    last = _extract_quote_value(quote, "last", "last_price", "lastPrice", "price")
    if bid is None or ask is None or last in (None, 0):
        return None
    return ((ask - bid) / last) * 100.0


def _price_band(price: float | None) -> str | None:
    if price is None:
        return None
    if price < 5:
        return "sub_5"
    if price < 20:
        return "5_to_20"
    if price < 100:
        return "20_to_100"
    return "100_plus"


def _premarket_bars(bars: list[dict[str, Any]], timezone_name: str) -> list[dict[str, Any]]:
    tz = ZoneInfo(timezone_name)
    out = []
    for bar in bars:
        ts = _bar_timestamp(bar)
        if not ts:
            continue
        local = ts.astimezone(tz)
        if time(4, 0) <= local.time() < time(9, 30):
            out.append(bar)
    return out


def _average_dollar_volume_from_daily_bars(md: Any, symbol: str, notes: list[str], limit: int = 20) -> float | None:
    if not hasattr(md, "get_bars_1d"):
        return None
    try:
        res = md.get_bars_1d(symbol, limit=limit)
    except Exception as exc:
        notes.append(f"daily_bars_unavailable:{exc}")
        return None
    if not isinstance(res, dict) or not res.get("ok"):
        notes.append(f"daily_bars_unavailable:{(res or {}).get('reason') if isinstance(res, dict) else 'unknown'}")
        return None
    bars = (res.get("bars") or []) if isinstance(res, dict) else []
    values = []
    for bar in bars:
        close = _f(bar.get("close") or bar.get("c") or bar.get("last"))
        volume = _f(bar.get("volume") or bar.get("v") or bar.get("vol"))
        if close is None or volume is None:
            continue
        values.append(close * volume)
    if not values:
        return None
    return sum(values[-limit:]) / min(len(values), limit)


def _execution_profile(last_price: float | None, avg20: float | None, premarket_dollar_volume: float | None, estimated_spread_pct: float | None, halt_status: str | None) -> tuple[float, list[str], list[str]]:
    score = 100.0
    blockers: list[str] = []
    warnings: list[str] = []
    if last_price is None:
        blockers.append("price_missing")
        score -= 40
    elif last_price < 3.0:
        blockers.append("price_below_execution_floor")
        score -= 30
    elif last_price < 5.0:
        warnings.append("price_below_default_band")
        score -= 10

    if avg20 is None:
        blockers.append("average_20d_dollar_volume_missing")
        score -= 25
    elif avg20 < 10_000_000:
        blockers.append("avg_dollar_volume_below_execution_floor")
        score -= 25
    elif avg20 < 25_000_000:
        warnings.append("avg_dollar_volume_below_default_band")
        score -= 10

    if premarket_dollar_volume is None:
        warnings.append("premarket_dollar_volume_missing")
        score -= 12
    elif premarket_dollar_volume < 1_000_000:
        warnings.append("premarket_dollar_volume_light")
        score -= 15

    if estimated_spread_pct is None:
        blockers.append("spread_estimate_missing")
        score -= 20
    elif estimated_spread_pct > 0.75:
        blockers.append("spread_too_wide")
        score -= 35
    elif estimated_spread_pct > 0.5:
        warnings.append("spread_wide")
        score -= 15

    if halt_status and halt_status.upper() not in {"NONE", "NO_HALT"}:
        blockers.append("halted")
        score -= 50

    return max(0.0, min(score, 100.0)), blockers, warnings


def classify_anti_chase_state(
    *,
    gap_pct: float | None,
    estimated_spread_pct: float | None,
    premarket_dollar_volume: float | None,
    execution_blockers: list[str] | None = None,
    catalyst_validated: bool = False,
    stale_prior_winner: bool = False,
) -> dict[str, Any]:
    """Classify whether a premarket runner is buyable now or only watchable.

    This is execution state, not research rank. A +40% catalyst runner can still
    be the research leader while requiring reset/reclaim evidence before entry.
    """

    blockers = list(execution_blockers or [])
    gap = abs(float(gap_pct or 0.0))
    spread = float(estimated_spread_pct or 0.0)
    dollar_volume = float(premarket_dollar_volume or 0.0)
    score = 72.0
    if stale_prior_winner:
        return {
            "anti_chase_state": lc.STALE_PRIOR_WINNER,
            "opportunity_lifecycle_state": lc.STALE_PRIOR_WINNER,
            "entry_viability_score": 0.0,
        }
    if blockers:
        score -= 35.0
    validated_liquid_runner = catalyst_validated and dollar_volume >= 1_000_000 and spread < 1.0 and not blockers
    if gap >= 60.0:
        if validated_liquid_runner:
            state = lc.SECOND_LEG_WATCH
            lifecycle = lc.SECOND_LEG_WATCH
            score -= 38.0
        else:
            state = lc.NO_TRADE_EXTENDED
            lifecycle = lc.NO_TRADE_EXTENDED
            score -= 45.0
    elif gap >= 25.0:
        state = lc.SECOND_LEG_WATCH if validated_liquid_runner else lc.EXTENDED_CHASE
        lifecycle = lc.SECOND_LEG_WATCH if validated_liquid_runner else lc.EXTENDED_CHASE
        score -= 28.0
    elif gap >= 10.0:
        state = lc.PREMARKET_BUILDING
        lifecycle = lc.PREMARKET_BUILDING
        score -= 8.0
    else:
        state = lc.PREMARKET_BUILDING
        lifecycle = lc.EARLY_CATALYST_DISCOVERY
    if spread >= 1.0:
        score -= 20.0
        if lifecycle == lc.PREMARKET_BUILDING:
            lifecycle = lc.SECOND_LEG_WATCH
            state = lc.SECOND_LEG_WATCH
    if dollar_volume >= 1_000_000 and catalyst_validated:
        score += 8.0
    return {
        "anti_chase_state": state,
        "opportunity_lifecycle_state": lifecycle,
        "entry_viability_score": round(max(0.0, min(100.0, score)), 3),
    }


def build_overlay_for_symbol(symbol: str, md: Any | None = None, cfg: dict[str, Any] | None = None) -> MarketOverlay:
    cfg = cfg or load_live_config()
    session = cfg.get("session") or {}
    md = md or build_market_data_adapter(cfg)

    quote_res = md.get_quote(symbol)
    bars_res = md.get_bars_1m(symbol, limit=500)
    now = datetime.now(timezone.utc).isoformat()

    notes: list[str] = []
    if not quote_res.get("ok"):
        notes.append(f"quote_unavailable:{quote_res.get('reason')}")
    if not bars_res.get("ok"):
        notes.append(f"bars_unavailable:{bars_res.get('reason')}")

    quote = quote_res.get("quote") or {}
    bars = bars_res.get("bars") or []
    premarket = _premarket_bars(bars if isinstance(bars, list) else [], session.get("timezone", "America/New_York"))

    prior_close = _extract_quote_value(quote, "prev_close", "previousClose", "prior_close")
    last_price = _extract_quote_value(quote, "last", "last_price", "lastPrice", "price")
    if prior_close is None and premarket:
        prior_close = _f((premarket[0] or {}).get("open") or (premarket[0] or {}).get("o"))
    if last_price is None and premarket:
        last_price = _f((premarket[-1] or {}).get("close") or (premarket[-1] or {}).get("c") or (premarket[-1] or {}).get("last"))
    gap_pct = None
    if prior_close not in (None, 0) and last_price is not None:
        gap_pct = ((last_price - prior_close) / prior_close) * 100.0

    volumes = [int(_f(bar.get("volume") or bar.get("v") or bar.get("vol")) or 0) for bar in premarket]
    closes = [_f(bar.get("close") or bar.get("c") or bar.get("last")) or 0.0 for bar in premarket]
    premarket_volume = sum(volumes) if premarket else None
    premarket_dollar_volume = sum(v * c for v, c in zip(volumes, closes)) if premarket else None

    estimated_spread_pct = _extract_spread_pct(quote)
    avg20 = _extract_quote_value(quote, "avg20dDollarVolume", "avg_dollar_volume_20d", "average_dollar_volume", "avg_daily_volume")
    if avg20 is None:
        avg20 = _average_dollar_volume_from_daily_bars(md, symbol, notes)
    market_cap = _extract_quote_value(quote, "market_cap", "marketCap")
    halt_status = str(quote.get("halt_status") or quote.get("haltStatus") or "NONE")

    readiness_score, blockers, warnings = _execution_profile(last_price, avg20, premarket_dollar_volume, estimated_spread_pct, halt_status)
    notes.extend(blockers + warnings)
    tradeability_pass = not blockers and readiness_score >= 60.0
    chase = classify_anti_chase_state(
        gap_pct=gap_pct,
        estimated_spread_pct=estimated_spread_pct,
        premarket_dollar_volume=premarket_dollar_volume,
        execution_blockers=blockers,
        catalyst_validated=False,
    )

    return MarketOverlay(
        ticker=symbol,
        observed_at=now,
        prior_close=round(prior_close, 4) if prior_close is not None else None,
        last_premarket_price=round(last_price, 4) if last_price is not None else None,
        gap_pct=round(gap_pct, 4) if gap_pct is not None else None,
        premarket_volume=premarket_volume,
        premarket_dollar_volume=round(premarket_dollar_volume, 2) if premarket_dollar_volume is not None else None,
        average_20d_dollar_volume=round(avg20, 2) if avg20 is not None else None,
        estimated_spread_pct=round(estimated_spread_pct, 4) if estimated_spread_pct is not None else None,
        halt_status=halt_status,
        market_cap=round(market_cap, 2) if market_cap is not None else None,
        price_band=_price_band(last_price),
        tradeability_gate_pass=tradeability_pass,
        tradeability_notes=notes,
        execution_readiness_score=round(readiness_score, 3),
        execution_blockers=blockers,
        execution_warnings=warnings,
        anti_chase_state=chase["anti_chase_state"],
        opportunity_lifecycle_state=chase["opportunity_lifecycle_state"],
        entry_viability_score=chase["entry_viability_score"],
    )


def build_market_overlays(symbols: list[str], md: Any | None = None, cfg: dict[str, Any] | None = None) -> dict[str, MarketOverlay]:
    cfg = cfg or load_live_config()
    md = md or build_market_data_adapter(cfg)
    unique_symbols: list[str] = []
    seen: set[str] = set()
    for raw_symbol in symbols:
        symbol = str(raw_symbol or "").upper().strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        unique_symbols.append(symbol)
    return {symbol: build_overlay_for_symbol(symbol, md=md, cfg=cfg) for symbol in unique_symbols}
