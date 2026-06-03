from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any

from .dedupe import dedupe_events, event_fingerprint, parse_ts
from .models import CandidateCluster


TICKER_DISPLAY_ALIASES = {
    "INFQ": ("INFQ", "INFLEQTION"),
}

EXHAUSTION_KEYWORDS = [
    "adds to gains",
    "after rally",
    "after soaring",
    "after surging",
    "extends gains",
    "extends rally",
    "follows rally",
    "parabolic",
    "profit taking",
    "second straight",
    "squeeze",
    "third straight",
]
CATALYST_TYPE_BASE_WEIGHTS = {
    "medical_or_biotech": 3.4,
    "mna_or_reorg": 3.3,
    "government_contract": 3.7,
    "earnings_or_guidance": 2.9,
    "earnings_or_material_update": 2.8,
    "product_or_partnership": 2.6,
    "exchange_mover": 1.8,
    "social_acceleration": 1.2,
    "obscure_catalyst_candidate": 2.0,
    "financing_or_balance_sheet": 1.1,
}


def _cluster_id(ticker: str, fingerprint: str) -> str:
    digest = hashlib.sha1(f"{ticker}|{fingerprint}".encode("utf-8")).hexdigest()[:12]
    return f"cluster_{digest}"


def _note_metric(notes: list[Any], prefix: str) -> float | None:
    for note in notes:
        text = str(note)
        if not text.startswith(prefix):
            continue
        try:
            return float(text.split("=", 1)[1])
        except Exception:
            return None
    return None


def _headline_text(bucket: list[dict[str, Any]]) -> str:
    return " ".join(
        str(part or "")
        for event in bucket
        for part in [event.get("headline"), event.get("raw_text")]
    ).lower()


def _exhaustion_signal(bucket: list[dict[str, Any]]) -> tuple[float, float | None, float | None, float]:
    text = _headline_text(bucket)
    keyword_hits = sum(1 for phrase in EXHAUSTION_KEYWORDS if phrase in text)
    max_gap = None
    max_mentions = 0.0
    max_premarket_dollar_volume = None
    for event in bucket:
        notes = list(event.get("notes") or [])
        gap = _note_metric(notes, "gap_pct=")
        mentions = _note_metric(notes, "mentions=") or 0.0
        pdv = _note_metric(notes, "premarket_dollar_volume=")
        if gap is not None:
            max_gap = gap if max_gap is None else max(max_gap, gap)
        max_mentions = max(max_mentions, mentions)
        if pdv is not None:
            max_premarket_dollar_volume = pdv if max_premarket_dollar_volume is None else max(max_premarket_dollar_volume, pdv)
    score = keyword_hits * 1.15
    if max_mentions >= 10:
        score += 1.1
    elif max_mentions >= 6:
        score += 0.6
    if max_gap is not None and max_gap >= 25:
        score += 1.3
    elif max_gap is not None and max_gap >= 12:
        score += 0.6
    if max_premarket_dollar_volume is not None and max_premarket_dollar_volume >= 5_000_000:
        score += 0.45
    return min(score, 10.0), max_gap, max_premarket_dollar_volume, max_mentions


def _catalyst_specific_adjustment(event: dict[str, Any]) -> float:
    text = f"{event.get('headline') or ''} {event.get('raw_text') or ''}".lower()
    catalyst_type = str(event.get("catalyst_type") or "")
    adjustment = 0.0
    if catalyst_type == "medical_or_biotech":
        if any(token in text for token in ["approval", "cleared", "clearance", "phase 3", "phase iii", "fast track", "pdufa"]):
            adjustment += 0.8
        elif any(token in text for token in ["phase 2", "phase ii", "trial data", "enrollment"]):
            adjustment += 0.45
    elif catalyst_type == "government_contract":
        if any(token in text for token in ["contract award", "department of defense", "army", "navy", "air force", "nasa"]):
            adjustment += 0.65
        if any(token in text for token in ["department of commerce", "commerce department", "chips", "grant", "funding", "letter of intent", "loi", "government equity", "equity stake", "quantum"]):
            adjustment += 0.85
    elif catalyst_type in {"earnings_or_guidance", "earnings_or_material_update"}:
        if any(token in text for token in ["raises guidance", "beat", "tops estimates", "record revenue"]):
            adjustment += 0.55
        if any(token in text for token in ["lowers guidance", "misses estimates"]):
            adjustment -= 0.6
    elif catalyst_type == "mna_or_reorg":
        if any(token in text for token in ["acquisition", "merger", "takeover", "buyout", "strategic alternatives"]):
            adjustment += 0.7
    elif catalyst_type == "product_or_partnership":
        if any(token in text for token in ["contract", "award", "partnership", "commercial launch", "collaboration"]):
            adjustment += 0.4
    elif catalyst_type == "financing_or_balance_sheet":
        if any(token in text for token in ["offering", "convertible", "private placement", "atm"]):
            adjustment -= 1.0
    return adjustment


def _catalyst_strength(bucket: list[dict[str, Any]], official_count: int, structured_count: int, social_count: int) -> float:
    score = 1.0
    for event in bucket:
        catalyst_type = str(event.get("catalyst_type") or "")
        score = max(score, CATALYST_TYPE_BASE_WEIGHTS.get(catalyst_type, 1.5) + _catalyst_specific_adjustment(event))
    score += min(2.0, official_count * 0.7)
    score += min(1.5, structured_count * 0.45)
    score += min(0.7, social_count * 0.15)
    return min(score, 10.0)


def _attention_score(bucket: list[dict[str, Any]], social_count: int) -> float:
    score = min(5.0, social_count * 1.2)
    for event in bucket:
        notes_text = " ".join(str(n) for n in (event.get("notes") or [])).lower()
        if "mentions=" in notes_text:
            for token in notes_text.split():
                if token.startswith("mentions="):
                    try:
                        score += min(2.0, float(token.split("=", 1)[1]) / 8.0)
                    except Exception:
                        pass
        headline = str(event.get("headline") or "").lower()
        if any(word in headline for word in ["surges", "spikes", "squeeze", "breakout", "jumps"]):
            score += 0.35
    return min(score, 10.0)


def _story_stage(freshness_score: float, crowdedness: float, exhaustion_score: float, max_gap: float | None, attention_score: float) -> float:
    if exhaustion_score >= 2.8 or crowdedness >= 8.6 or (max_gap is not None and max_gap >= 25 and attention_score >= 4.0):
        return 2.5
    if freshness_score >= 8.0 and crowdedness <= 3.0 and exhaustion_score < 1.0:
        return 9.0
    if freshness_score >= 6.0 and crowdedness <= 6.0:
        return 7.0
    if crowdedness >= 7.0:
        return 4.0
    return 5.5


def _asymmetry_score(
    cluster_price_hint: float | None,
    official_count: int,
    structured_count: int,
    freshness_score: float,
    attention_score: float,
    crowdedness: float,
    obscure_count: int,
    exhaustion_score: float,
    max_gap: float | None,
) -> float:
    score = 2.5 + min(2.5, freshness_score * 0.25) + min(2.0, attention_score * 0.2)
    if official_count and structured_count:
        score += 1.1
    if obscure_count:
        score += min(1.5, obscure_count * 0.4)
    if crowdedness <= 4.0:
        score += 1.1
    elif crowdedness >= 8.0:
        score -= 1.5
    if cluster_price_hint is not None and cluster_price_hint <= 20:
        score += 0.8
    if exhaustion_score >= 2.8:
        score -= 1.35
    elif exhaustion_score >= 1.5:
        score -= 0.6
    if max_gap is not None and max_gap >= 20:
        score -= 0.75
    return max(0.0, min(score, 10.0))


def select_claim_summary_for_ticker(ticker: str, events: list[dict[str, Any]]) -> str:
    symbol = str(ticker or "").upper().strip()
    aliases = tuple({symbol, *TICKER_DISPLAY_ALIASES.get(symbol, ())})

    def direct_score(event: dict[str, Any]) -> tuple[int, str]:
        headline = str(event.get("headline") or "")
        raw_text = str(event.get("raw_text") or "")
        company_name = str(event.get("company_name") or "")
        haystack = " ".join([headline, raw_text, company_name]).upper()
        title = headline.upper()
        direct_alias = any(alias and alias.upper() in haystack for alias in aliases)
        direct_title = any(alias and alias.upper() in title for alias in aliases)
        explicit_theme = bool(symbol and title.startswith(f"{symbol} "))
        synthetic_theme = str(event.get("source_name") or "") == "theme_basket_scout"
        official = bool(event.get("official_flag"))
        structured = bool(event.get("structured_flag"))
        if synthetic_theme and (direct_title or explicit_theme):
            score = 3
        elif direct_title or explicit_theme:
            score = 5
        elif direct_alias:
            score = 4
        elif official and symbol and symbol in haystack:
            score = 3
        elif structured and direct_alias:
            score = 2
        else:
            score = 1
        return (score, str(event.get("published_at") or event.get("discovered_at") or ""))

    ranked = sorted(events or [], key=direct_score, reverse=True)
    return str((ranked[0] if ranked else {}).get("headline") or "")


def cluster_events(events: list[dict[str, Any]]) -> list[CandidateCluster]:
    deduped = dedupe_events(events)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in deduped:
        tickers = [str(t).upper() for t in (event.get("ticker_candidates") or []) if str(t).strip()]
        if not tickers:
            continue
        primary_ticker = tickers[0]
        grouped[(primary_ticker, event_fingerprint(event))].append(event)

    clusters: list[CandidateCluster] = []
    for (ticker, fingerprint), bucket in grouped.items():
        bucket_sorted = sorted(bucket, key=lambda item: item.get("published_at") or item.get("discovered_at") or "")
        catalyst_counts = Counter(str(item.get("catalyst_type") or "unknown") for item in bucket_sorted)
        company_names = [item.get("company_name") for item in bucket_sorted if item.get("company_name")]
        official_sources = sorted({item.get("source_url") for item in bucket_sorted if item.get("official_flag") and item.get("source_url")})
        structured_sources = sorted({item.get("source_url") for item in bucket_sorted if item.get("structured_flag") and item.get("source_url")})
        social_sources = sorted({item.get("source_url") for item in bucket_sorted if item.get("social_flag") and item.get("source_url")})
        obscure_sources = sorted({item.get("source_url") for item in bucket_sorted if not item.get("official_flag") and not item.get("structured_flag") and not item.get("social_flag") and item.get("source_url")})
        first_seen = min((item.get("published_at") or item.get("discovered_at") or "" for item in bucket_sorted), default="")
        latest_update = max((item.get("updated_at") or item.get("published_at") or item.get("discovered_at") or "" for item in bucket_sorted), default="")
        freshness_score = 0.0
        latest_ts = parse_ts(latest_update)
        first_ts = parse_ts(first_seen)
        if latest_ts and first_ts and latest_ts >= first_ts:
            cluster_age_hours = (latest_ts - first_ts).total_seconds() / 3600.0
            freshness_score = max(freshness_score, max(0.0, 10.0 - cluster_age_hours))
        for item in bucket_sorted:
            hours = item.get("freshness_hours")
            if isinstance(hours, (int, float)):
                freshness_score = max(freshness_score, max(0.0, 10.0 - float(hours)))
        source_scores = [float(item.get("credibility_score_initial") or 0.0) for item in bucket_sorted]
        claim_summary = select_claim_summary_for_ticker(ticker, bucket_sorted)
        official_count = len(official_sources)
        structured_count = len(structured_sources)
        social_count = len(social_sources)
        obscure_count = len(obscure_sources)
        attention_score = _attention_score(bucket_sorted, social_count)
        exhaustion_score, max_gap, _max_premarket_dollar_volume, _max_mentions = _exhaustion_signal(bucket_sorted)
        crowdedness = min(
            10.0,
            max(
                0.0,
                len(structured_sources)
                + len(social_sources) * 0.65
                + max(0, len(bucket_sorted) - 1) * 0.35
                + min(1.5, attention_score * 0.12)
                + exhaustion_score,
            ),
        )
        if official_count and freshness_score >= 8.0 and exhaustion_score < 1.0 and (max_gap is None or max_gap < 8.0):
            crowdedness = max(0.0, crowdedness - 0.75)
        catalyst_strength = _catalyst_strength(bucket_sorted, official_count, structured_count, social_count)
        price_hint = None
        for item in bucket_sorted:
            notes = item.get("notes") or []
            for note in notes:
                text = str(note)
                if text.startswith("price="):
                    try:
                        price_hint = float(text.split("=", 1)[1])
                    except Exception:
                        pass
        story_stage_score = _story_stage(freshness_score, crowdedness, exhaustion_score, max_gap, attention_score)
        asymmetry_score = _asymmetry_score(price_hint, official_count, structured_count, freshness_score, attention_score, crowdedness, obscure_count, exhaustion_score, max_gap)
        research_priority_score = max(
            0.0,
            min(
                10.0,
                catalyst_strength * 0.35
                + freshness_score * 0.22
                + attention_score * 0.15
                + asymmetry_score * 0.18
                + (sum(source_scores) / len(source_scores) if source_scores else 0.0) * 0.10
                - crowdedness * 0.08,
            ),
        )
        clusters.append(
            CandidateCluster(
                cluster_id=_cluster_id(ticker, fingerprint),
                primary_ticker=ticker,
                company_name=company_names[0] if company_names else None,
                events=bucket_sorted,
                catalyst_type_primary=catalyst_counts.most_common(1)[0][0],
                catalyst_types_all=sorted(catalyst_counts.keys()),
                first_seen_at=first_seen,
                latest_update_at=latest_update,
                official_sources=official_sources,
                structured_sources=structured_sources,
                social_sources=social_sources,
                obscure_sources=obscure_sources,
                claim_summary=claim_summary,
                official_confirmed=bool(official_sources),
                source_quality_score=round(sum(source_scores) / len(source_scores), 3) if source_scores else 0.0,
                freshness_score=round(freshness_score, 3),
                crowdedness_preliminary=round(crowdedness, 3),
                unresolved_questions=[],
                elimination_flags=[],
                official_confirmation_count=official_count,
                structured_confirmation_count=structured_count,
                social_confirmation_count=social_count,
                obscure_confirmation_count=obscure_count,
                catalyst_strength_score=round(catalyst_strength, 3),
                attention_acceleration_score=round(attention_score, 3),
                story_stage_score=round(story_stage_score, 3),
                asymmetry_score=round(asymmetry_score, 3),
                research_priority_score=round(research_priority_score, 3),
            )
        )

    clusters.sort(key=lambda item: (item.research_priority_score, item.catalyst_strength_score, item.freshness_score), reverse=True)
    return clusters
