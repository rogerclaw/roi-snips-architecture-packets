from __future__ import annotations

from collections import defaultdict
from typing import Any


EXCLUDED_TICKER_SUFFIXES = {"W", "WS", "U", "RT", "R", "P"}
MEGACAP_PENALTY_TICKERS = {"AAPL", "AMZN", "AMD", "GOOG", "GOOGL", "META", "MSFT", "NFLX", "NVDA", "PLTR", "QQQ", "SMCI", "SPY", "TSLA"}
CATALYST_TYPE_BONUS = {
    "medical_or_biotech": 1.5,
    "mna_or_reorg": 1.35,
    "government_contract": 1.8,
    "earnings_or_guidance": 1.05,
    "earnings_or_material_update": 1.0,
    "product_or_partnership": 0.85,
    "obscure_catalyst_candidate": 0.9,
    "social_acceleration": 0.2,
    "exchange_mover": 0.15,
}


def _valid_symbol(symbol: str) -> bool:
    symbol = str(symbol or "").strip().upper()
    if not symbol or len(symbol) > 5:
        return False
    if not symbol.isalnum():
        return False
    if symbol.endswith(tuple(EXCLUDED_TICKER_SUFFIXES)) and len(symbol) > 3:
        return False
    return True


def extract_symbol_candidates(events: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    added: set[str] = set()
    for event in events:
        for raw_symbol in event.get("ticker_candidates") or []:
            symbol = str(raw_symbol or "").upper().strip()
            if not _valid_symbol(symbol) or symbol in added:
                continue
            added.add(symbol)
            seen.append(symbol)
    return seen


def _event_score(event: dict[str, Any], symbol: str) -> float:
    base = 0.0
    if event.get("official_flag"):
        base += 6.0
    if event.get("structured_flag"):
        base += 4.0
    if event.get("social_flag"):
        base += 1.5
    freshness_hours = event.get("freshness_hours")
    if isinstance(freshness_hours, (int, float)):
        base += max(0.0, 3.0 - min(float(freshness_hours), 3.0))
    notes = [str(note).lower() for note in (event.get("notes") or [])]
    base += min(1.5, len(notes) * 0.15)
    credibility = float(event.get("credibility_score_initial") or 0.0)
    base += min(2.0, credibility / 5.0)
    base += CATALYST_TYPE_BONUS.get(str(event.get("catalyst_type") or ""), 0.0)
    headline = f"{event.get('headline') or ''} {event.get('raw_text') or ''}".lower()
    if str(event.get("catalyst_type") or "") == "government_contract" and any(
        token in headline
        for token in ["chips", "department of commerce", "commerce department", "grant", "funding", "letter of intent", "loi", "government equity", "equity stake", "quantum"]
    ):
        base += 1.0
    if any("lesser_known_candidate" in note for note in notes):
        base += 0.9
    if event.get("official_flag") and event.get("structured_flag"):
        base += 0.5
    if symbol in MEGACAP_PENALTY_TICKERS:
        base -= 1.3
        if event.get("official_flag") and float(event.get("credibility_score_initial") or 0.0) >= 8.0:
            base += 0.5
    if event.get("social_flag") and not event.get("official_flag") and not event.get("structured_flag"):
        base -= 0.6
    return base


def derive_candidate_universe(
    events: list[dict[str, Any]],
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    max_symbols: int = 40,
) -> list[str]:
    include = [str(s).upper().strip() for s in (include or []) if _valid_symbol(str(s))]
    excluded = {str(s).upper().strip() for s in (exclude or []) if str(s).strip()}

    scores: dict[str, float] = defaultdict(float)
    touches: dict[str, int] = defaultdict(int)
    source_diversity: dict[str, set[str]] = defaultdict(set)
    for event in events:
        raw_symbols = event.get("ticker_candidates") or []
        for raw_symbol in raw_symbols:
            symbol = str(raw_symbol or "").upper().strip()
            if not _valid_symbol(symbol) or symbol in excluded:
                continue
            scores[symbol] += _event_score(event, symbol)
            touches[symbol] += 1
            source_diversity[symbol].add(str(event.get("source_name") or "unknown"))

    for symbol, names in source_diversity.items():
        scores[symbol] += min(1.2, max(0, len(names) - 1) * 0.35)

    for symbol in include:
        if symbol in excluded:
            continue
        scores[symbol] += 1000.0
        touches[symbol] += 1

    ranked = sorted(
        scores,
        key=lambda symbol: (scores[symbol], touches[symbol], len(source_diversity[symbol]), -len(symbol), symbol),
        reverse=True,
    )
    return ranked[: max(1, int(max_symbols))] if ranked else include[: max(1, int(max_symbols))]
