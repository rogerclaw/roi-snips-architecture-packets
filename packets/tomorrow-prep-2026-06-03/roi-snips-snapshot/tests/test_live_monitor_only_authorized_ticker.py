import json

from src.workflows import live_monitor

from tests.test_trade_authorization_ticket import valid_ticket


def test_live_monitor_loads_ticket_ticker_not_watchlist(tmp_path, monkeypatch):
    ticket_path = tmp_path / "ticket.json"
    ticket_path.write_text(json.dumps(valid_ticket("INFQ")))
    monkeypatch.setenv("ROI_SNIPS_TRADE_AUTHORIZATION_TICKET_PATH", str(ticket_path))
    rows = live_monitor._load_active_watchlist(tmp_path)
    assert [row["symbol"] for row in rows] == ["INFQ"]


def test_live_monitor_does_not_fall_back_to_morning_packet_without_ticket(tmp_path, monkeypatch):
    monkeypatch.setenv("ROI_SNIPS_TRADE_AUTHORIZATION_TICKET_PATH", str(tmp_path / "missing_ticket.json"))
    packet_dir = tmp_path / "reports" / "morning" / "json"
    packet_dir.mkdir(parents=True)
    packet_dir.joinpath("2026-05-29.json").write_text(
        json.dumps(
            {
                "trade_authorization": {"authorized": True, "ticker": "NVDA"},
                "best_pick_candidate": {"ticker": "NVDA", "symbol": "NVDA"},
                "watchlist": {"A": [{"ticker": "NVDA"}]},
            }
        )
    )

    assert live_monitor._load_active_watchlist(tmp_path) == []


def test_live_monitor_rejects_proposal_not_in_ticket():
    ok, reason = live_monitor._validate_ticket_for_submission({"ticker": "NVDA", "mode": "ORB_BREAK"}, valid_ticket("INFQ"))
    assert ok is False
    assert reason == "unauthorized_ticker_not_in_deep_research_ticket"
