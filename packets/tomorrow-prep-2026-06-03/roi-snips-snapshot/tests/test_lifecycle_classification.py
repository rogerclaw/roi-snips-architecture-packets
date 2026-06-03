from src.research import lifecycle as lc
from src.research.market_overlay import classify_anti_chase_state


def test_lifecycle_separates_research_leader_from_buy_now_state() -> None:
    early = classify_anti_chase_state(gap_pct=8, estimated_spread_pct=0.2, premarket_dollar_volume=2_000_000, catalyst_validated=True)
    extended = classify_anti_chase_state(gap_pct=35, estimated_spread_pct=0.2, premarket_dollar_volume=2_000_000, catalyst_validated=True)
    stale = classify_anti_chase_state(gap_pct=8, estimated_spread_pct=0.2, premarket_dollar_volume=2_000_000, stale_prior_winner=True)

    assert early["opportunity_lifecycle_state"] in {lc.EARLY_CATALYST_DISCOVERY, lc.PREMARKET_BUILDING}
    assert extended["anti_chase_state"] == lc.SECOND_LEG_WATCH
    assert stale["opportunity_lifecycle_state"] == lc.STALE_PRIOR_WINNER
