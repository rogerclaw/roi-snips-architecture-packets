from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from ...common.time_utils import utc_now_iso
from ..models import RawEvent


def freshness_hours(published_at: str | None, now: str | None = None) -> float | None:
    if not published_at:
        return None
    try:
        published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00")).astimezone(timezone.utc)
        current = datetime.fromisoformat(str(now or utc_now_iso()).replace("Z", "+00:00")).astimezone(timezone.utc)
        return round(max(0.0, (current - published).total_seconds() / 3600.0), 3)
    except Exception:
        return None


def event_id_for(source_name: str, source_url: str, headline: str, ticker: str | None = None) -> str:
    base = f"{source_name}|{source_url}|{headline}|{ticker or ''}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:14]
    return f"evt_{digest}"


def raw_event(
    *,
    source_name: str,
    source_tier: int,
    source_url: str,
    headline: str,
    raw_text: str,
    company_name: str | None,
    ticker_candidates: list[str],
    catalyst_type: str,
    official_flag: bool,
    structured_flag: bool,
    social_flag: bool,
    credibility_score_initial: float,
    extraction_confidence: float,
    published_at: str | None = None,
    updated_at: str | None = None,
    notes: list[str] | None = None,
) -> RawEvent:
    discovered_at = utc_now_iso()
    return RawEvent(
        event_id=event_id_for(source_name, source_url, headline, (ticker_candidates or [None])[0]),
        source_name=source_name,
        source_tier=source_tier,
        source_url=source_url,
        discovered_at=discovered_at,
        published_at=published_at,
        updated_at=updated_at,
        headline=headline,
        raw_text=raw_text,
        company_name=company_name,
        ticker_candidates=[str(t).upper() for t in ticker_candidates if str(t).strip()],
        catalyst_type=catalyst_type,
        official_flag=official_flag,
        structured_flag=structured_flag,
        social_flag=social_flag,
        credibility_score_initial=credibility_score_initial,
        freshness_hours=freshness_hours(published_at, discovered_at),
        extraction_confidence=extraction_confidence,
        notes=notes or [],
    )
