from src.research.dedupe import dedupe_events, event_fingerprint


def test_event_fingerprint_is_stable():
    event = {
        "ticker_candidates": ["NVDA"],
        "catalyst_type": "earnings_or_guidance",
        "headline": "NVIDIA announces earnings beat",
        "raw_text": "NVIDIA announces earnings beat and guidance raise",
    }
    assert event_fingerprint(event).startswith("NVDA|earnings_or_guidance|")


def test_dedupe_events_removes_same_claim_within_window():
    events = [
        {
            "ticker_candidates": ["NVDA"],
            "source_name": "sec_edgar",
            "catalyst_type": "earnings_or_guidance",
            "headline": "NVIDIA announces earnings beat",
            "raw_text": "beat and raise",
            "published_at": "2026-04-15T10:00:00+00:00",
            "discovered_at": "2026-04-15T10:01:00+00:00",
        },
        {
            "ticker_candidates": ["NVDA"],
            "source_name": "sec_edgar",
            "catalyst_type": "earnings_or_guidance",
            "headline": "NVIDIA announces earnings beat",
            "raw_text": "beat and raise",
            "published_at": "2026-04-15T11:00:00+00:00",
            "discovered_at": "2026-04-15T11:01:00+00:00",
        },
    ]
    assert len(dedupe_events(events)) == 1
