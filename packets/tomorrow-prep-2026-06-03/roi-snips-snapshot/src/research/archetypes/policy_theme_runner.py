from __future__ import annotations

from typing import Any

from ..models import CandidateCluster, MarketOverlay


MEGACAP_TICKERS = {"AAPL", "AMZN", "AMD", "GOOG", "GOOGL", "IBM", "META", "MSFT", "NFLX", "NVDA", "PLTR", "QQQ", "SMCI", "SPY", "TSLA"}


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


def _text(cluster: CandidateCluster) -> str:
    parts = [
        str(getattr(cluster, "primary_ticker", "") or ""),
        str(getattr(cluster, "company_name", "") or ""),
        str(getattr(cluster, "claim_summary", "") or ""),
        str(getattr(cluster, "catalyst_type_primary", "") or ""),
        " ".join(str(item) for item in getattr(cluster, "catalyst_types_all", []) or []),
    ]
    for event in getattr(cluster, "events", []) or []:
        parts.extend(
            [
                str(event.get("company_name") or ""),
                str(event.get("headline") or ""),
                str(event.get("raw_text") or ""),
                " ".join(str(note) for note in event.get("notes") or []),
            ]
        )
    return " ".join(parts).lower()


def _contains(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def _overlay_value(overlay: MarketOverlay | dict[str, Any] | None, attr: str) -> float:
    if overlay is None:
        return 0.0
    if hasattr(overlay, attr):
        return float(getattr(overlay, attr) or 0.0)
    return float((overlay or {}).get(attr) or 0.0)


def _note_metric(cluster: CandidateCluster, prefix: str) -> float:
    for event in cluster.events:
        for note in event.get("notes") or []:
            raw = str(note)
            if raw.startswith(prefix):
                try:
                    return float(raw.split("=", 1)[1])
                except Exception:
                    return 0.0
    return 0.0


def score_policy_theme_runner_archetype(cluster: CandidateCluster, overlay: MarketOverlay | dict[str, Any] | None = None) -> dict[str, Any]:
    """Ticker-neutral score for high-beta policy/theme direct beneficiaries.

    This intentionally does not call the old INFQ scorer. It rewards direct
    policy/funding/theme benefit, undercovered high-beta names, fresh validation,
    and premarket repricing while penalizing stale prior winners and mega-cap
    sympathy drift.
    """

    text = _text(cluster)
    catalyst_types = {str(getattr(cluster, "catalyst_type_primary", "") or ""), *[str(item) for item in getattr(cluster, "catalyst_types_all", []) or []]}
    ticker = str(getattr(cluster, "primary_ticker", "") or "").upper()
    gap = max(abs(_overlay_value(overlay, "gap_pct")), abs(_note_metric(cluster, "gap_pct=")))
    dollar_volume = max(_overlay_value(overlay, "premarket_dollar_volume"), _note_metric(cluster, "premarket_dollar_volume="))

    policy_terms = ["government", "department of commerce", "commerce department", "chips", "chips act", "grant", "funding", "contract", "award", "letter of intent", "loi", "sam.gov", "usaspending", "fda", "clinical trial"]
    theme_terms = ["quantum", "ai", "semiconductor", "energy", "defense", "biotech", "cancer", "rare disease", "battery", "nuclear", "space"]
    direct_terms = ["receives", "awarded", "selected", "beneficiary", "direct", "contracted", "funded", "letter of intent", "collaboration with", "partnership with"]
    validation_terms = ["benzinga", "press release", "sec", "8-k", "analyst", "price target", "newswire", "company announced"]
    stale_terms = ["yesterday", "last week", "prior winner", "already ran", "stale", "old news"]
    indirect_terms = ["sympathy", "sector mention", "basket", "etf", "peer", "mentioned alongside"]
    supply_terms = ["offering", "atm", "warrant", "dilution", "registered direct", "s-1", "s-3"]

    government_or_policy = 3.0 if catalyst_types.intersection({"government_contract", "regulatory", "clinical_trial"}) else 0.0
    if _contains(text, policy_terms):
        government_or_policy += 4.0
    sector_theme = 2.0 + (3.0 if _contains(text, theme_terms) else 0.0)
    direct_beneficiary = 2.0 + (4.5 if _contains(text, direct_terms) else 0.0)
    if ticker and ticker not in MEGACAP_TICKERS:
        direct_beneficiary += 1.2
    undercovered = 2.0 if ticker in MEGACAP_TICKERS else 7.0
    if _contains(text, ["spac", "new public", "undercovered", "microcap", "small-cap", "small cap"]):
        undercovered += 1.5
    high_beta = min(10.0, (gap / 4.0) + (2.0 if dollar_volume >= 1_000_000 else 0.0))
    premarket_repricing = min(10.0, gap / 2.5)
    professional_validation = min(10.0, float(getattr(cluster, "structured_confirmation_count", 0) or 0) * 2.0 + float(getattr(cluster, "official_confirmation_count", 0) or 0) * 2.0)
    if _contains(text, validation_terms):
        professional_validation += 1.0
    social_retail = min(10.0, float(getattr(cluster, "attention_acceleration_score", 0.0) or 0.0) + min(3.0, float(getattr(cluster, "social_confirmation_count", 0) or 0)))
    same_day_event = 7.0 if _contains(text, ["today", "this morning", "conference", "symposium", "fireside", "presentation"]) else 0.0

    stale_penalty = 5.0 if _contains(text, stale_terms) else 0.0
    mega_cap_sympathy_penalty = 6.5 if ticker in MEGACAP_TICKERS else 0.0
    indirect_penalty = 3.5 if _contains(text, indirect_terms) and not _contains(text, direct_terms) else 0.0
    chase_penalty = 2.5 if gap >= 35.0 else 0.0
    supply_penalty = 4.0 if _contains(text, supply_terms) else 0.0

    components = {
        "government_policy_score": _clamp(government_or_policy),
        "sector_theme_score": _clamp(sector_theme),
        "direct_beneficiary_score": _clamp(direct_beneficiary),
        "undercovered_ticker_score": _clamp(undercovered),
        "high_beta_theme_score": _clamp(high_beta),
        "premarket_repricing_score": _clamp(premarket_repricing),
        "structured_validation_score": _clamp(professional_validation),
        "social_retail_score": _clamp(social_retail),
        "same_day_event_score": _clamp(same_day_event),
        "stale_prior_winner_penalty": _clamp(stale_penalty),
        "mega_cap_sympathy_penalty": _clamp(mega_cap_sympathy_penalty),
        "indirect_sector_mention_penalty": _clamp(indirect_penalty),
        "exhausted_chase_penalty": _clamp(chase_penalty),
        "dilution_or_supply_penalty": _clamp(supply_penalty),
    }
    score = (
        0.16 * components["government_policy_score"]
        + 0.12 * components["sector_theme_score"]
        + 0.16 * components["direct_beneficiary_score"]
        + 0.12 * components["undercovered_ticker_score"]
        + 0.10 * components["high_beta_theme_score"]
        + 0.10 * components["premarket_repricing_score"]
        + 0.10 * components["structured_validation_score"]
        + 0.06 * components["social_retail_score"]
        + 0.04 * components["same_day_event_score"]
        - 0.12 * components["stale_prior_winner_penalty"]
        - 0.10 * components["mega_cap_sympathy_penalty"]
        - 0.08 * components["indirect_sector_mention_penalty"]
        - 0.06 * components["exhausted_chase_penalty"]
        - 0.06 * components["dilution_or_supply_penalty"]
    )
    tags: list[str] = []
    if score >= 5.5:
        tags.append("POLICY_THEME_RUNNER_ARCHETYPE")
    if components["direct_beneficiary_score"] >= 6.0:
        tags.append("DIRECT_POLICY_THEME_BENEFICIARY")
    if components["stale_prior_winner_penalty"] >= 5.0:
        tags.append("STALE_PRIOR_WINNER")
    if components["mega_cap_sympathy_penalty"] >= 5.0:
        tags.append("MEGACAP_SYMPATHY_DEMOTED")
    return {
        "policy_theme_runner_score": round(_clamp(score), 3),
        "infq_archetype_score": round(_clamp(score), 3),
        "components": {key: round(value, 3) for key, value in components.items()},
        "tags": sorted(tags),
    }
