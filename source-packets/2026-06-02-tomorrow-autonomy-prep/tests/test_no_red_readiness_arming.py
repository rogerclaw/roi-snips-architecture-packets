from src.workflows import final_live_arming_gate

from tests.test_trade_authorization_ticket import valid_ticket


def test_red_readiness_cannot_arm_even_with_valid_ticket(monkeypatch):
    actions = []
    monkeypatch.setenv("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION", "true")
    monkeypatch.setenv("ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION", "false")
    monkeypatch.setattr(final_live_arming_gate, "load_live_config", lambda: {})
    monkeypatch.setattr(final_live_arming_gate, "load_today_ticket", lambda root, trade_date=None: valid_ticket("INFQ"))
    monkeypatch.setattr(
        final_live_arming_gate,
        "check_opening_bell_readiness",
        lambda ignore_arm_guards=False, **kwargs: {"status": "RED", "opening_bell_blockers": ["INFQ:no_immediately_available_entry_mode"]},
    )
    monkeypatch.setattr(final_live_arming_gate, "activate_flag", lambda name, reason="", cfg=None: actions.append(("activate", name)))
    monkeypatch.setattr(final_live_arming_gate, "clear_flag", lambda name, cfg=None: actions.append(("clear", name)))
    monkeypatch.setattr(final_live_arming_gate, "active_guards", lambda cfg, **kwargs: {"live_armed": False, "disable_entries": True})
    monkeypatch.setattr(final_live_arming_gate, "_write_json", lambda path, payload: None)

    result = final_live_arming_gate.run_final_live_arming_gate(execute=True)
    assert result["verdict"] == "NO_GO"
    assert result["pre_open_standby_override"] is False
    assert ("activate", "live_armed") not in actions
