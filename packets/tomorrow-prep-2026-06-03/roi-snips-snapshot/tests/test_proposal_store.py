from src.execution.proposal_store import find_recent_matching_proposal, list_proposals, load_proposal, save_proposal, update_proposal


CFG = {
    "controls": {
        "kill_switch_file": "/tmp/roi-snips-test-kill",
        "disable_entries_file": "/tmp/roi-snips-test-disable",
        "telegram_offset_file": "/tmp/roi-snips-test-offset",
        "proposals_dir": "/tmp/roi-snips-test-proposals-store",
        "operator_events_dir": "/tmp/roi-snips-test-ops-store",
    }
}


def test_save_and_update_proposal(tmp_path):
    cfg = {
        "controls": {
            **CFG["controls"],
            "proposals_dir": str(tmp_path / "proposals"),
        }
    }
    proposal = {"plan_id": "plan_store_1", "ticker": "AAPL", "status": "ready_for_execution"}
    save_proposal(proposal, cfg)
    loaded = load_proposal("plan_store_1", cfg)
    assert loaded["ticker"] == "AAPL"

    update_proposal("plan_store_1", {"status": "previewed_dry_run"}, cfg)
    updated = load_proposal("plan_store_1", cfg)
    assert updated["status"] == "previewed_dry_run"
    assert len(list_proposals(cfg=cfg)) == 1
    assert find_recent_matching_proposal("AAPL", "ORB_BREAK", cfg=cfg) is None


def test_find_recent_matching_proposal(tmp_path):
    cfg = {
        "controls": {
            **CFG["controls"],
            "proposals_dir": str(tmp_path / "proposals"),
        }
    }
    save_proposal({"plan_id": "plan_store_2", "ticker": "NVDA", "trigger": "ORB_BREAK", "status": "ready_for_execution"}, cfg)
    found = find_recent_matching_proposal("NVDA", "ORB_BREAK", cfg=cfg)
    assert found is not None
    assert found["plan_id"] == "plan_store_2"
