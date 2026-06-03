import json
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_sender():
    script = ROOT / "scripts" / "send_morning_update.py"
    spec = importlib.util.spec_from_file_location("send_morning_update", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_compose_morning_update_includes_pick_and_no_order_reason(tmp_path: Path) -> None:
    day = "2026-05-28"
    (tmp_path / "reports/morning/json").mkdir(parents=True)
    (tmp_path / "reports/live_monitor").mkdir(parents=True)
    (tmp_path / f"runs/{day}/normalized").mkdir(parents=True)

    (tmp_path / f"reports/morning/json/{day}.json").write_text(
        json.dumps(
            {
                "symbols_considered": ["INFQ", "AAPL", "NVDA"],
                "raw_candidate_count": 9,
                "enriched_candidate_count": 8,
                "best_pick_candidate": {
                    "symbol": "INFQ",
                    "catalyst_type": "sector_theme_wave",
                    "claim_summary": "INFQ exchange mover candidate",
                    "last_price": 15.96,
                    "gap_pct": 2.5707,
                    "premarket_dollar_volume": 22923192.53,
                    "spread_pct": 0.3759,
                    "execution_gate_pass": True,
                },
                "research_ranked": [{"symbol": "INFQ"}, {"symbol": "AAPL"}, {"symbol": "NVDA"}],
                "source_lane_status": [{"lane_name": "Alpaca News", "ran": True, "useful_evidence_count": 16}],
                "deep_research_route": None,
            }
        )
    )
    (tmp_path / f"reports/live_monitor/next_open_shadow_validation_{day}.json").write_text(
        json.dumps(
            {
                "orders_allowed": False,
                "orders_submitted": False,
                "broker_account_inspected": False,
                "broker_orders_inspected": False,
                "broker_positions_inspected": False,
                "status": "OK",
                "all_steps_ok_or_shadow_allowed": True,
                "stream": {"proposal_count": 0, "blocked_proposal_count": 0, "fired_symbols": []},
            }
        )
    )
    (tmp_path / f"runs/{day}/normalized/daily_best_pick_packet.json").write_text(
        json.dumps({"suggested_buy_zone": "Use live tape.", "thesis_break_level": "VWAP loss."})
    )

    message = _load_sender().compose_message(tmp_path, day)

    assert "picked INFQ as primary" in message
    assert "No-order validation: PASS (OK)." in message
    assert "Mode: no-order shadow only" in message
    assert "orders_allowed=False, orders_submitted=False" in message
    assert "Broker account/orders/positions inspected: False/False/False" in message
    assert "proposals=0" in message


def test_compose_morning_update_warns_when_validation_failed(tmp_path: Path) -> None:
    day = "2026-05-29"
    (tmp_path / "reports/morning/json").mkdir(parents=True)
    (tmp_path / "reports/live_monitor").mkdir(parents=True)
    (tmp_path / f"runs/{day}/normalized").mkdir(parents=True)

    (tmp_path / f"reports/morning/json/{day}.json").write_text(
        json.dumps(
            {
                "symbols_considered": ["ABCD"],
                "raw_candidate_count": 12,
                "enriched_candidate_count": 1,
                "best_pick_candidate": {"symbol": "ABCD", "catalyst_type": "fresh catalyst"},
                "research_ranked": [{"symbol": "ABCD"}],
            }
        )
    )
    (tmp_path / f"reports/live_monitor/next_open_shadow_validation_{day}.json").write_text(
        json.dumps(
            {
                "status": "SHADOW_INVALID",
                "all_steps_ok_or_shadow_allowed": False,
                "orders_allowed": False,
                "orders_submitted": False,
                "broker_account_inspected": False,
                "broker_orders_inspected": False,
                "broker_positions_inspected": False,
                "stream": {"proposal_count": 0, "blocked_proposal_count": 0, "fired_symbols": []},
            }
        )
    )

    message = _load_sender().compose_message(tmp_path, day)

    assert "No-order validation: NOT CLEAN (SHADOW_INVALID)." in message
    assert "Do not treat this as a ready trading readout" in message
    assert "orders_allowed=False, orders_submitted=False" in message


def test_compose_morning_update_handles_market_closed_without_fake_pick(tmp_path: Path) -> None:
    day = "2026-05-29"
    (tmp_path / "reports/morning/json").mkdir(parents=True)
    (tmp_path / "reports/live_monitor").mkdir(parents=True)

    (tmp_path / f"reports/morning/json/{day}.json").write_text(
        json.dumps(
            {
                "status": "market_closed",
                "market_session": {"next_open": "2026-06-01T09:30:00-04:00"},
                "best_pick_candidate": None,
            }
        )
    )
    (tmp_path / f"reports/live_monitor/next_open_shadow_validation_{day}.json").write_text(
        json.dumps(
            {
                "status": "OK",
                "all_steps_ok_or_shadow_allowed": True,
                "orders_allowed": False,
                "orders_submitted": False,
                "broker_account_inspected": False,
                "broker_orders_inspected": False,
                "broker_positions_inspected": False,
            }
        )
    )

    message = _load_sender().compose_message(tmp_path, day)

    assert "market is closed for this run, so there is no pick" in message
    assert "picked none" not in message
    assert "Next market open: 2026-06-01T09:30:00-04:00" in message
