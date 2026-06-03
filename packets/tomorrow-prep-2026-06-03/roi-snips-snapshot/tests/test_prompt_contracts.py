from pathlib import Path

from src.research.final_packet_schema import validate_final_packet
from src.research.prompt_runner import build_prompt_packet


def test_prompt_pack_loads_without_running_external_models() -> None:
    packet = build_prompt_packet(["00_MASTER_MISSION.md"], context={"mode": "brokerless"})

    assert packet["status"] == "PROMPTS_LOADED"
    assert packet["prompt_count"] == 1
    assert "Roi Snips" in packet["prompts"][0]["body"]


def test_final_packet_schema_requires_reportable_trade_fields() -> None:
    validation = validate_final_packet({"ticker": "ABCD", "catalyst": "fresh catalyst"})

    assert validation.valid is False
    assert "buy_zone" in validation.missing_fields
    assert "source_breadth_status" in validation.missing_fields
    assert "why_not_blue_chip" in validation.missing_fields
    assert "why_not_stale_prior_winner" in validation.missing_fields
