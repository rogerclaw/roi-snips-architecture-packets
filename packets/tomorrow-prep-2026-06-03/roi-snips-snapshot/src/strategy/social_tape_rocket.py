"""SOCIAL_TAPE_ROCKET qualification.

This strategy intentionally separates discovery from execution. Social/X/Reddit
attention can put a symbol on the live tape watchlist, but it cannot trade until
price, volume, spread, and opening-drive tape confirm.
"""

from __future__ import annotations

from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def evaluate_social_tape_rocket(candidate: dict[str, Any], tape: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or {}
    thresholds = ((cfg.get("opening_bell") or {}).get("social_tape_rocket") or {}) if isinstance(cfg, dict) else {}
    min_attention = float(thresholds.get("min_attention_acceleration_score", 8.0))
    min_hyper = float(thresholds.get("min_hyper_trade_score", 7.0))
    min_drive = float(thresholds.get("min_opening_drive_score", 7.2))
    min_volume = float(thresholds.get("min_volume_burst_score", 6.5))
    max_spread_bps = float(thresholds.get("max_spread_bps", 200.0))

    attention = _f(candidate.get("attention_acceleration_score") or candidate.get("social_attention_velocity"))
    hyper = _f(candidate.get("hyper_trade_score"))
    drive = _f(tape.get("opening_drive_score"))
    volume = min(10.0, _f(tape.get("volume_burst_ratio")))
    spread = _f(tape.get("spread_bps"), 9999.0)
    social_only = candidate.get("validation_status") == "social_discovery_only" or (
        _f(candidate.get("official_confirmation_count")) == 0 and _f(candidate.get("structured_confirmation_count")) == 0
    )
    tape_confirms = bool(
        tape.get("premarket_high_break_confirmed")
        or tape.get("premarket_high_reclaim_confirmed")
        or tape.get("micro_vwap_hold")
        or tape.get("price_above_open")
    )
    predicates = {
        "attention_acceleration_ok": attention >= min_attention,
        "hyper_trade_score_ok": hyper >= min_hyper,
        "opening_drive_score_ok": drive >= min_drive,
        "volume_burst_ok": volume >= min_volume,
        "spread_tradeable": spread <= max_spread_bps,
        "tape_confirmation_present": tape_confirms,
    }
    failed = [key for key, value in predicates.items() if not value]
    payload = {
        "strategy": "SOCIAL_TAPE_ROCKET",
        "passed_predicates": [key for key, value in predicates.items() if value],
        "failed_predicates": failed,
        "actuals": {
            "attention_acceleration_score": attention,
            "hyper_trade_score": hyper,
            "opening_drive_score": drive,
            "volume_burst_score": volume,
            "spread_bps": spread,
            "social_only": social_only,
            "tape_state": tape.get("tape_state"),
        },
        "thresholds": {
            "min_attention_acceleration_score": min_attention,
            "min_hyper_trade_score": min_hyper,
            "min_opening_drive_score": min_drive,
            "min_volume_burst_score": min_volume,
            "max_spread_bps": max_spread_bps,
        },
    }
    if social_only:
        return {
            "action": "WAIT",
            "reason": "social_discovery_requires_official_or_structured_confirmation",
            **payload,
            "failed_predicates": sorted(set([*failed, "official_or_structured_confirmation_present"])),
        }
    if failed:
        return {"action": "NO_TRADE", "reason": "social_tape_rocket_not_confirmed", **payload}
    return {"action": "BUY_NOW", "reason": "social_tape_rocket_confirmed", **payload}
