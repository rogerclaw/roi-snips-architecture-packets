from src.research.first_seen import classify_first_seen_stage, merge_first_seen_records


def test_first_seen_preserves_original_discovery_and_updates_move() -> None:
    existing = {
        "INFQ": {
            "ticker": "INFQ",
            "first_seen_at_utc": "2026-05-27T12:00:00+00:00",
            "first_seen_price": 10.0,
            "first_seen_gap_pct": 6.0,
        }
    }

    rows = merge_first_seen_records(existing, [{"ticker": "INFQ", "price": 12.5, "gap_pct": 25.0}], selected_at_utc="2026-05-27T13:00:00+00:00")

    assert rows[0]["first_seen_at_utc"] == "2026-05-27T12:00:00+00:00"
    assert rows[0]["current_price"] == 12.5
    assert rows[0]["move_since_first_seen_pct"] == 25.0
    assert rows[0]["first_seen_stage"] == "ALREADY_MOVING"


def test_first_seen_classifies_late_and_stale_prior_winners() -> None:
    assert classify_first_seen_stage(first_seen_gap_pct=41) == "LATE_DISCOVERY"
    assert classify_first_seen_stage(first_seen_gap_pct=3, stale_prior_winner=True) == "STALE_PRIOR_WINNER"
