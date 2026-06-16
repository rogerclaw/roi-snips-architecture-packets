from __future__ import annotations

from typing import Any

from ..models import CandidateCluster, MarketOverlay


MEGACAP_TICKERS = {"AAPL", "AMZN", "AMD", "GOOG", "GOOGL", "META", "MSFT", "NFLX", "NVDA", "PLTR", "QQQ", "SMCI", "SPY", "TSLA", "IBM"}


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


def _text(cluster: CandidateCluster) -> str:
    parts: list[str] = [
        str(cluster.claim_summary or ""),
        str(cluster.catalyst_type_primary or ""),
        " ".join(str(item) for item in (cluster.catalyst_types_all or [])),
    ]
    for event in cluster.events:
        parts.extend(
            [
                str(event.get("headline") or ""),
                str(event.get("raw_text") or ""),
                " ".join(str(note) for note in (event.get("notes") or [])),
            ]
        )
    return " ".join(parts).lower()


def _contains(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def _note_metric(cluster: CandidateCluster, prefix: str) -> float | None:
    for event in cluster.events:
        for note in event.get("notes") or []:
            raw = str(note)
            if not raw.startswith(prefix):
                continue
            try:
                return float(raw.split("=", 1)[1])
            except Exception:
                return None
    return None


def _overlay_gap(overlay: MarketOverlay | dict[str, Any] | None) -> float:
    if overlay is None:
        return 0.0
    if hasattr(overlay, "gap_pct"):
        return float(getattr(overlay, "gap_pct") or 0.0)
    return float((overlay or {}).get("gap_pct") or 0.0)


def _overlay_dollar_volume(overlay: MarketOverlay | dict[str, Any] | None) -> float:
    if overlay is None:
        return 0.0
    if hasattr(overlay, "premarket_dollar_volume"):
        return float(getattr(overlay, "premarket_dollar_volume") or 0.0)
    return float((overlay or {}).get("premarket_dollar_volume") or 0.0)


def score_infq_archetype(cluster: CandidateCluster, overlay: MarketOverlay | dict[str, Any] | None = None) -> dict[str, Any]:
    """Score the high-beta hard-catalyst runner Charles expected Roi Snips to find.

    The score is intentionally research-oriented. It does not make a candidate
    executable; broker, data, liquidity, stream, and order gates still decide
    whether any trade can be placed.
    """

    text = _text(cluster)
    catalyst_types = {str(cluster.catalyst_type_primary or ""), *[str(t) for t in (cluster.catalyst_types_all or [])]}
    government_terms = ["government", "department of commerce", "commerce department", "chips", "chips act", "grant", "funding", "letter of intent", "loi", "government equity", "equity stake", "contract award"]
    quantum_terms = ["quantum", "quantum computing", "qubit"]
    sector_terms = ["sector basket", "sector wave", "sympathy", "qbts", "rgti", "qubt", "ionq", "gfs", "ibm"]
    event_terms = ["investor event", "symposium", "fireside chat", "conference today", "presents today"]
    validation_terms = ["analyst", "price target", "benzinga", "press", "newswire", "seeking alpha", "motley fool"]
    supply_terms = ["offering", "atm", "warrant", "redemption", "s-1", "s-3", "dilution", "registered direct"]

    gap = max(abs(_overlay_gap(overlay)), abs(_note_metric(cluster, "gap_pct=") or 0.0))
    dollar_volume = max(_overlay_dollar_volume(overlay), _note_metric(cluster, "premarket_dollar_volume=") or 0.0)
    social_mentions = _note_metric(cluster, "mentions=") or float(cluster.social_confirmation_count or len(cluster.social_sources))

    material_catalyst = 0.0
    if "government_contract" in catalyst_types:
        material_catalyst += 5.0
    if _contains(text, government_terms):
        material_catalyst += 3.2
    if _contains(text, quantum_terms):
        material_catalyst += 1.4

    sector_wave = 1.0
    if _contains(text, quantum_terms):
        sector_wave += 2.8
    if _contains(text, sector_terms):
        sector_wave += 3.4

    direct_beneficiary = 4.0 if _contains(text, government_terms + quantum_terms) else 1.5
    if "government_contract" in catalyst_types and _contains(text, quantum_terms):
        direct_beneficiary += 2.5

    premarket_repricing = min(10.0, gap / 2.0)
    if dollar_volume >= 5_000_000:
        premarket_volume_quality = 9.0
    elif dollar_volume >= 1_000_000:
        premarket_volume_quality = 7.2
    elif dollar_volume >= 250_000:
        premarket_volume_quality = 5.4
    else:
        premarket_volume_quality = 2.5 if gap else 0.0

    undercovered = 4.5
    if cluster.primary_ticker not in MEGACAP_TICKERS:
        undercovered += 2.4
    if _contains(text, ["new public", "spac", "undercovered", "lesser known", "discovery phase"]):
        undercovered += 2.0
    if cluster.obscure_confirmation_count or cluster.obscure_sources:
        undercovered += 1.0

    social_velocity = min(10.0, float(cluster.attention_acceleration_score or 0.0) + min(3.0, social_mentions / 4.0))
    professional_validation = min(10.0, float(cluster.structured_confirmation_count or len(cluster.structured_sources)) * 2.2 + float(cluster.official_confirmation_count or len(cluster.official_sources)) * 1.5)
    if _contains(text, validation_terms):
        professional_validation += 1.0
    same_day_event = 8.5 if _contains(text, event_terms) else 0.0
    level_clarity = min(10.0, float(cluster.asymmetry_score or 0.0) + (1.2 if gap else 0.0) + (1.0 if dollar_volume else 0.0))
    exhaustion_penalty = 2.5 if gap >= 25 else max(0.0, float(cluster.crowdedness_preliminary or 0.0) - 7.0)
    dilution_supply_penalty = 4.0 if _contains(text, supply_terms) else 0.0
    mega_cap_penalty = 8.0 if cluster.primary_ticker in MEGACAP_TICKERS else 0.0

    components = {
        "material_catalyst_score": _clamp(material_catalyst),
        "sector_wave_score": _clamp(sector_wave),
        "direct_beneficiary_score": _clamp(direct_beneficiary),
        "premarket_repricing_score": _clamp(premarket_repricing),
        "premarket_volume_quality": _clamp(premarket_volume_quality),
        "undercovered_discovery_score": _clamp(undercovered),
        "social_attention_velocity": _clamp(social_velocity),
        "professional_validation_score": _clamp(professional_validation),
        "same_day_event_score": _clamp(same_day_event),
        "level_clarity_score": _clamp(level_clarity),
        "exhaustion_penalty": _clamp(exhaustion_penalty),
        "dilution_or_supply_penalty": _clamp(dilution_supply_penalty),
        "mega_cap_boring_penalty": _clamp(mega_cap_penalty),
    }
    score = (
        0.18 * components["material_catalyst_score"]
        + 0.16 * components["sector_wave_score"]
        + 0.14 * components["direct_beneficiary_score"]
        + 0.12 * components["premarket_repricing_score"]
        + 0.10 * components["premarket_volume_quality"]
        + 0.10 * components["undercovered_discovery_score"]
        + 0.08 * components["social_attention_velocity"]
        + 0.06 * components["professional_validation_score"]
        + 0.04 * components["same_day_event_score"]
        + 0.02 * components["level_clarity_score"]
        - 0.08 * components["exhaustion_penalty"]
        - 0.06 * components["dilution_or_supply_penalty"]
        - 0.10 * components["mega_cap_boring_penalty"]
    )
    tags: list[str] = []
    if components["material_catalyst_score"] >= 7.0 and components["sector_wave_score"] >= 6.0:
        tags.append("INFQ_STYLE_GOVERNMENT_SECTOR_WAVE")
    if components["undercovered_discovery_score"] >= 7.0:
        tags.append("UNDERCOVERED_HIGH_BETA")
    if components["same_day_event_score"] >= 7.0:
        tags.append("SAME_DAY_EVENT_VISIBILITY")
    return {"infq_archetype_score": round(_clamp(score), 3), "components": {k: round(v, 3) for k, v in components.items()}, "tags": tags}
