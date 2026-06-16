from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _text(payload: dict[str, Any] | str) -> str:
    if isinstance(payload, str):
        return payload.lower()
    parts = [
        str(payload.get("headline") or ""),
        str(payload.get("raw_text") or ""),
        str(payload.get("summary") or ""),
        " ".join(str(note) for note in (payload.get("notes") or [])),
    ]
    return " ".join(parts).lower()


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def analyze_sec_materiality(payload: dict[str, Any] | str, *, as_of: datetime | None = None) -> dict[str, Any]:
    text = _text(payload)
    as_of = as_of or datetime.now(timezone.utc)
    published = _parse_ts(payload.get("published_at") or payload.get("updated_at") if isinstance(payload, dict) else None)
    staleness_days = None
    if published is not None:
        staleness_days = max(0.0, (as_of - published).total_seconds() / 86400.0)

    routine_terms = ["10-q", "10-k", "quarterly report", "annual report", "form 10q", "form 10-k"]
    material_terms = ["definitive agreement", "material agreement", "contract", "customer", "government", "department of commerce", "chips", "grant", "funding", "merger", "acquisition", "guidance", "raises guidance", "strategic alternatives"]
    offering_terms = ["offering", "registered direct", "atm", "at-the-market", "s-1", "s-3", "convertible", "private placement"]
    warrant_terms = ["warrant", "redemption", "$18", "exercise price", "earnout"]

    routine = any(term in text for term in routine_terms)
    material_hits = sum(1 for term in material_terms if term in text)
    offering = any(term in text for term in offering_terms)
    warrant = any(term in text for term in warrant_terms)
    stale = bool(staleness_days is not None and staleness_days > 3.0)

    catalyst_specificity = min(10.0, material_hits * 2.0)
    if routine and material_hits == 0:
        catalyst_specificity = min(catalyst_specificity, 2.0)
    materiality = min(10.0, 2.0 + catalyst_specificity + (1.0 if "8-k" in text else 0.0))
    if routine and material_hits == 0:
        materiality = min(materiality, 3.0)
    if stale:
        materiality = max(0.0, materiality - 2.0)

    dilution_risk = 0.0
    if offering:
        dilution_risk += 5.0
    if warrant:
        dilution_risk += 2.5

    generic_penalty = 0.0
    if routine and material_hits == 0:
        generic_penalty += 4.0
    if "8-k" in text and material_hits == 0:
        generic_penalty += 2.5
    if stale:
        generic_penalty += 2.0
    if offering:
        generic_penalty += 1.5

    if materiality >= 7.0:
        label = "material_current_catalyst"
    elif generic_penalty >= 4.0:
        label = "generic_or_stale_filing"
    elif offering or warrant:
        label = "supply_risk"
    else:
        label = "low_materiality"

    return {
        "sec_materiality_score_0_10": round(max(0.0, min(10.0, materiality)), 3),
        "filing_staleness_days": round(staleness_days, 3) if staleness_days is not None else None,
        "catalyst_specificity_score_0_10": round(max(0.0, min(10.0, catalyst_specificity)), 3),
        "dilution_risk_score_0_10": round(max(0.0, min(10.0, dilution_risk)), 3),
        "warrant_supply_zone_detected": warrant,
        "offering_or_atm_detected": offering,
        "generic_sec_filing_penalty": round(max(0.0, min(10.0, generic_penalty)), 3),
        "materiality_label": label,
    }
