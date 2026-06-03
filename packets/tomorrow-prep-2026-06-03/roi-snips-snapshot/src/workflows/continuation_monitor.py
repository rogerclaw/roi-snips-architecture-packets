from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..strategy.orb_breakout import evaluate_orb_breakout
from ..strategy.premarket_high_reclaim import evaluate_premarket_high_reclaim
from ..strategy.second_leg_continuation import evaluate_second_leg_continuation
from ..strategy.vwap_washout_reclaim import evaluate_vwap_washout_reclaim


@dataclass
class ContinuationMonitorResult:
    status: str
    symbol: str
    continuation_engine: dict[str, Any]
    decisions: list[dict[str, Any]] = field(default_factory=list)
    broker_action: str = "NONE"
    orders_submitted: bool = False
    generated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _series(bars: list[dict[str, Any]], key: str) -> list[float]:
    out: list[float] = []
    aliases = {
        "close": ["close", "c", "last"],
        "low": ["low", "l"],
        "high": ["high", "h"],
        "volume": ["volume", "v", "vol"],
        "vwap": ["vwap", "vw"],
    }[key]
    for bar in bars:
        for alias in aliases:
            if alias in bar:
                try:
                    out.append(float(bar[alias]))
                    break
                except Exception:
                    continue
    return out


def build_continuation_monitor(
    candidate: dict[str, Any],
    bars: list[dict[str, Any]],
    tape: dict[str, Any] | None = None,
) -> ContinuationMonitorResult:
    tape = tape or {}
    symbol = str(candidate.get("ticker") or candidate.get("symbol") or "").upper()
    closes = _series(bars, "close")
    lows = _series(bars, "low")
    highs = _series(bars, "high")
    volumes = _series(bars, "volume")
    vwaps = _series(bars, "vwap") or closes
    spread_bps = float(tape.get("spread_bps", 50.0))

    decisions: list[dict[str, Any]] = []
    second_leg = evaluate_second_leg_continuation(
        symbol=symbol,
        closes=closes,
        lows=lows,
        highs=highs,
        volumes=volumes,
        vwaps=vwaps,
        spread_bps=spread_bps,
        premarket_high=candidate.get("premarket_high") or tape.get("premarket_high"),
        opening_range_high=tape.get("opening_range_high"),
        opening_range_low=tape.get("opening_range_low"),
    )
    decisions.append(second_leg)

    latest_tape = dict(tape)
    if closes:
        latest_tape.setdefault("last", closes[-1])
        latest_tape.setdefault("price", closes[-1])
    if vwaps:
        latest_tape.setdefault("vwap", vwaps[-1])
    decisions.extend(
        [
            evaluate_premarket_high_reclaim(candidate, latest_tape),
            evaluate_vwap_washout_reclaim(candidate, latest_tape),
            evaluate_orb_breakout(candidate, latest_tape, minutes=1),
            evaluate_orb_breakout(candidate, latest_tape, minutes=5),
        ]
    )
    buy_signals = [row for row in decisions if row.get("action") == "BUY_NOW"]
    status = "SIGNAL_READY" if buy_signals else "WAIT"
    engine = {
        "engine": "continuation_monitor",
        "status": status,
        "broker_action": "NONE",
        "orders_submitted": False,
        "second_leg": second_leg.get("action") == "BUY_NOW",
        "premarket_high_reclaim": any(row.get("mode") == "PREMARKET_HIGH_RECLAIM" and row.get("action") == "BUY_NOW" for row in decisions),
        "vwap_washout_reclaim": any(row.get("mode") == "VWAP_WASHOUT_RECLAIM" and row.get("action") == "BUY_NOW" for row in decisions),
        "orb_breakout": any(str(row.get("mode", "")).startswith("ORB_BREAK") and row.get("action") == "BUY_NOW" for row in decisions),
        "buy_signal_count": len(buy_signals),
    }
    return ContinuationMonitorResult(status=status, symbol=symbol, continuation_engine=engine, decisions=decisions)
