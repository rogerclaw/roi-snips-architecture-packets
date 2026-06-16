from src.workflows.deep_mini_bridge import parse_deep_mini_output
from tests.runbook_helpers import ranked_row


def test_morning_best_pick_packet_has_required_final_fields() -> None:
    output = """
# Executive summary
INFQ is the best asymmetric setup.
# Best pick: INFQ
Suggested buy zone: Wait for VWAP reclaim near 12.
Same-day upside target: 14-15.
1-3 day upside target: 16-18.
Thesis-break level: Below 11.
# Ranked backups
- QTUM: same theme backup
# Key invalidation risks
- Loses VWAP on fading volume
# Monitoring timeframes
- 09:30-11:00 ET
# Profit-taking triggers
- Scale into vertical spike
# Danger signals
- Offering headline
"""
    packet = parse_deep_mini_output(output, [ranked_row("INFQ")], {"route_chosen": "deep_mini"}).to_dict()

    assert packet["best_pick"] == "INFQ"
    assert packet["suggested_buy_zone"]
    assert packet["same_day_upside_target"]
    assert packet["one_to_three_day_upside_target"]
    assert packet["thesis_break_level"]
    assert packet["monitoring_timeframes"]
    assert packet["profit_taking_triggers"]
    assert packet["danger_signals"]
