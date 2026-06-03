from src.research.stale_winner_memory import evaluate_stale_winner


def test_stale_prior_winner_cannot_execute_without_fresh_catalyst_and_live_tape() -> None:
    result = evaluate_stale_winner(
        "INFQ",
        {"INFQ": {"picked_at": "2026-05-27T12:00:00+00:00"}},
        has_fresh_catalyst=False,
        has_live_tape_confirmation=False,
        now="2026-05-28T14:00:00+00:00",
    )

    assert result.executable is False
    assert result.prior_session_count_checked == 1
    assert "prior_winner_without_fresh_catalyst" in result.blockers
    assert "prior_winner_without_live_tape_confirmation" in result.blockers


def test_stale_winner_checks_last_ten_research_leader_and_primary_sessions() -> None:
    sessions = [
        {"research_leader": f"OLD{i}", "executable_primary": None, "trading_date": f"2026-05-{10+i:02d}"}
        for i in range(9)
    ] + [{"research_leader": "INFQ", "executable_primary": "ABCD", "trading_date": "2026-05-27"}]

    result = evaluate_stale_winner(
        "INFQ",
        sessions,
        has_fresh_catalyst=False,
        has_live_tape_confirmation=True,
        now="2026-05-28T14:00:00+00:00",
    )

    assert result.stale_prior_winner is True
    assert result.prior_session_count_checked == 10
    assert result.recent_roles == ["research_leader"]
    assert "prior_winner_without_fresh_catalyst" in result.blockers
