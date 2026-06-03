from src.research.source_lane_status import REQUIRED_SOURCE_LANES, build_source_lane_status
from tests.runbook_helpers import event


def test_source_lane_status_reports_required_lanes_and_primary_impact() -> None:
    rows = build_source_lane_status(
        [
            event("INFQ", source_name="sec_edgar", official=True),
            event("BWIN", source_name="grok_x", official=False, social=True, url="https://x.com/post"),
        ],
        primary_ticker="INFQ",
    )
    by_lane = {row["lane_name"]: row for row in rows}

    assert set(REQUIRED_SOURCE_LANES).issubset(by_lane)
    assert by_lane["SEC EDGAR"]["ran"] is True
    assert by_lane["SEC EDGAR"]["useful_for_primary"] is True
    assert by_lane["Grok/X"]["affected_backup_list"] is True
