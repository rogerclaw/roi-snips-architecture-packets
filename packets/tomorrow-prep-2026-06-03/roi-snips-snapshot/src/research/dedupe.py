from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


NON_WORD_RE = re.compile(r"[^a-z0-9]+")
STOPWORDS = {"inc", "corp", "corporation", "company", "co", "ltd", "plc", "class", "shares", "announces", "reports", "update"}


def normalize_text(text: str) -> str:
    lowered = NON_WORD_RE.sub(" ", (text or "").lower()).strip()
    tokens = [tok for tok in lowered.split() if tok and tok not in STOPWORDS]
    return " ".join(tokens)


def normalize_catalyst_label(label: str) -> str:
    value = normalize_text(label).replace(" ", "_")
    return value or "unknown"


def normalize_claim(headline: str, raw_text: str = "") -> str:
    combined = normalize_text(f"{headline} {raw_text}")
    tokens = combined.split()[:18]
    return " ".join(tokens)


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def within_hours(a: str | None, b: str | None, hours: int = 24) -> bool:
    ta = parse_ts(a)
    tb = parse_ts(b)
    if not ta or not tb:
        return False
    return abs((ta - tb).total_seconds()) <= (hours * 3600)


def event_fingerprint(event: dict[str, Any]) -> str:
    ticker = ((event.get("ticker_candidates") or ["UNK"])[0] or "UNK").upper()
    catalyst = normalize_catalyst_label(str(event.get("catalyst_type") or "unknown"))
    claim = normalize_claim(str(event.get("headline") or ""), str(event.get("raw_text") or ""))
    return f"{ticker}|{catalyst}|{claim}"


def dedupe_events(events: list[dict[str, Any]], hours: int = 24) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    seen: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        fingerprint = event_fingerprint(event)
        bucket = seen.setdefault(fingerprint, [])
        duplicate = False
        for prior in bucket:
            same_source = str(event.get("source_name") or "") == str(prior.get("source_name") or "")
            if same_source and within_hours(event.get("published_at") or event.get("discovered_at"), prior.get("published_at") or prior.get("discovered_at"), hours=hours):
                duplicate = True
                break
        if duplicate:
            continue
        bucket.append(event)
        kept.append(event)
    return kept
