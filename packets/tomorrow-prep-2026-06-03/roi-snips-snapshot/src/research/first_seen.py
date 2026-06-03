from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FIRST_SEEN_PATH = "normalized/first_seen_candidates.json"


def _f(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def classify_first_seen_stage(
    *,
    first_seen_gap_pct: float | None,
    move_since_first_seen_pct: float | None = None,
    stale_prior_winner: bool = False,
) -> str:
    if stale_prior_winner:
        return "STALE_PRIOR_WINNER"
    gap = abs(float(first_seen_gap_pct or 0.0))
    move = abs(float(move_since_first_seen_pct or 0.0))
    if gap >= 40.0 or move >= 40.0:
        return "LATE_DISCOVERY"
    if gap >= 20.0 or move >= 20.0:
        return "ALREADY_MOVING"
    if gap >= 5.0:
        return "PREMARKET_BUILDING"
    return "EARLY_SEED"


@dataclass
class FirstSeenRecord:
    ticker: str
    first_seen_at_utc: str
    first_seen_source: str | None = None
    first_seen_source_url: str | None = None
    first_seen_catalyst: str | None = None
    first_seen_price: float | None = None
    first_seen_gap_pct: float | None = None
    first_seen_premarket_volume: int | None = None
    first_seen_premarket_dollar_volume: float | None = None
    current_price: float | None = None
    current_gap_pct: float | None = None
    move_since_first_seen_pct: float | None = None
    first_seen_to_selection_minutes: float | None = None
    first_seen_stage: str = "EARLY_SEED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def candidate_to_first_seen_record(candidate: dict[str, Any], *, selected_at_utc: str | None = None) -> FirstSeenRecord:
    ticker = str(candidate.get("ticker") or candidate.get("symbol") or "").upper().strip()
    first_seen_at = str(candidate.get("first_seen_at_utc") or candidate.get("first_seen_at") or candidate.get("discovered_at") or datetime.now(timezone.utc).isoformat())
    first_price = _f(candidate.get("first_seen_price") or candidate.get("price") or candidate.get("last_price") or candidate.get("current_price"))
    current_price = _f(candidate.get("current_price") or candidate.get("last_price") or candidate.get("price") or first_price)
    first_gap = _f(candidate.get("first_seen_gap_pct") or candidate.get("gap_pct") or candidate.get("current_gap_pct"))
    current_gap = _f(candidate.get("current_gap_pct") or candidate.get("gap_pct") or first_gap)
    move_since = None
    if first_price not in (None, 0) and current_price is not None:
        move_since = ((current_price - first_price) / first_price) * 100.0
    first_dt = _dt(first_seen_at)
    selected_dt = _dt(selected_at_utc) or datetime.now(timezone.utc)
    minutes = None
    if first_dt:
        minutes = max(0.0, (selected_dt - first_dt).total_seconds() / 60.0)
    return FirstSeenRecord(
        ticker=ticker,
        first_seen_at_utc=first_seen_at,
        first_seen_source=candidate.get("first_seen_source") or candidate.get("source_lane") or candidate.get("source_name"),
        first_seen_source_url=candidate.get("first_seen_source_url") or candidate.get("raw_source_url") or candidate.get("source_url"),
        first_seen_catalyst=candidate.get("first_seen_catalyst") or candidate.get("raw_catalyst") or candidate.get("catalyst_summary") or candidate.get("raw_reason"),
        first_seen_price=round(first_price, 4) if first_price is not None else None,
        first_seen_gap_pct=round(first_gap, 4) if first_gap is not None else None,
        first_seen_premarket_volume=int(candidate.get("first_seen_premarket_volume") or candidate.get("premarket_volume") or 0) or None,
        first_seen_premarket_dollar_volume=_f(candidate.get("first_seen_premarket_dollar_volume") or candidate.get("premarket_dollar_volume")),
        current_price=round(current_price, 4) if current_price is not None else None,
        current_gap_pct=round(current_gap, 4) if current_gap is not None else None,
        move_since_first_seen_pct=round(move_since, 4) if move_since is not None else None,
        first_seen_to_selection_minutes=round(minutes, 3) if minutes is not None else None,
        first_seen_stage=classify_first_seen_stage(
            first_seen_gap_pct=first_gap,
            move_since_first_seen_pct=move_since,
            stale_prior_winner=bool(candidate.get("stale_prior_winner")),
        ),
    )


def load_first_seen(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        import json

        data = json.loads(path.read_text())
    except Exception:
        return {}
    if isinstance(data, dict):
        rows = data.values()
    else:
        rows = data if isinstance(data, list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = str((row or {}).get("ticker") or "").upper().strip()
        if ticker:
            out[ticker] = dict(row)
    return out


def merge_first_seen_records(existing: dict[str, dict[str, Any]], candidates: list[dict[str, Any]], *, selected_at_utc: str | None = None) -> list[dict[str, Any]]:
    merged = {str(k).upper(): dict(v) for k, v in existing.items()}
    for candidate in candidates:
        ticker = str(candidate.get("ticker") or candidate.get("symbol") or "").upper().strip()
        if not ticker:
            continue
        current = candidate_to_first_seen_record(candidate, selected_at_utc=selected_at_utc).to_dict()
        previous = merged.get(ticker)
        if previous and previous.get("first_seen_at_utc") and previous.get("first_seen_price") is not None:
            first_price = _f(previous.get("first_seen_price"))
            current_price = _f(candidate.get("current_price") or candidate.get("last_price") or candidate.get("price") or current.get("current_price"))
            if first_price not in (None, 0) and current_price is not None:
                previous["current_price"] = round(current_price, 4)
                previous["move_since_first_seen_pct"] = round(((current_price - first_price) / first_price) * 100.0, 4)
                previous["current_gap_pct"] = _f(candidate.get("current_gap_pct") or candidate.get("gap_pct") or previous.get("current_gap_pct"))
                previous["first_seen_stage"] = classify_first_seen_stage(
                    first_seen_gap_pct=_f(previous.get("first_seen_gap_pct")),
                    move_since_first_seen_pct=_f(previous.get("move_since_first_seen_pct")),
                    stale_prior_winner=bool(candidate.get("stale_prior_winner") or previous.get("first_seen_stage") == "STALE_PRIOR_WINNER"),
                )
            merged[ticker] = previous
        else:
            merged[ticker] = current
    return [merged[key] for key in sorted(merged)]
