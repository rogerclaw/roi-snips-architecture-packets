from src.research import lifecycle as lc
from src.research.market_overlay import classify_anti_chase_state


def test_anti_chase_blocks_unvalidated_extended_gaps() -> None:
    state = classify_anti_chase_state(gap_pct=65, estimated_spread_pct=1.2, premarket_dollar_volume=200_000, catalyst_validated=False)

    assert state["anti_chase_state"] == lc.NO_TRADE_EXTENDED
    assert state["entry_viability_score"] < 40
