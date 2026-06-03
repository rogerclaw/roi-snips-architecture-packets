from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_premarket_wrapper_keeps_live_order_submission_disabled() -> None:
    body = (ROOT / "scripts" / "run_live_trade_ready_premarket.sh").read_text()

    assert 'ROI_SNIPS_SKIP_DEEP_MINI="${ROI_SNIPS_SKIP_DEEP_MINI:-false}"' in body
    assert 'ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH:-true}"' in body
    assert 'ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH:-false}"' in body
    assert "export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=false" in body
    assert "export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=true" not in body
    assert "preview_order" not in body
    assert "place_order" not in body


def test_live_opening_wrapper_is_the_order_authority_surface() -> None:
    body = (ROOT / "scripts" / "run_live_opening_trade_ready.sh").read_text()

    assert "export ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=true" in body
    assert 'ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH:-true}"' in body
    assert 'ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH="${ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH:-false}"' in body
    assert "supervise_opening_bell_live_monitor.sh" in body
