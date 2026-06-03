import json
from types import SimpleNamespace

from src.research.storage import ResearchRunStorage
from src.workflows.research_pipeline import ResearchPipeline, _manual_symbol_overrides, _merge_ranked_by_ticker


class StubScout:
    def __init__(self, events):
        self.events = events

    def collect(self, tickers=None):
        return list(self.events)


def test_manual_symbol_overrides_has_no_hardcoded_fallback(monkeypatch):
    monkeypatch.delenv("ROI_SNIPS_SYMBOLS", raising=False)
    assert _manual_symbol_overrides() == []


def test_merge_ranked_by_ticker_consolidates_multiple_infq_events():
    rows = [
        {
            "ticker": "INFQ",
            "research_priority_score": 7.8,
            "hyper_trade_score": 8.1,
            "lane_tags": ["VERIFIED_CATALYST_RUNNER"],
            "cluster": {
                "primary_ticker": "INFQ",
                "claim_summary": "INFQ receives CHIPS funding LOI",
                "events": [
                    {
                        "source_name": "benzinga",
                        "source_url": "https://example.com/infq-bz",
                        "headline": "INFQ receives CHIPS funding LOI",
                        "published_at": "2026-05-21T12:00:00+00:00",
                        "structured_flag": True,
                    }
                ],
                "structured_sources": ["https://example.com/infq-bz"],
                "official_sources": [],
                "social_sources": [],
                "obscure_sources": [],
                "catalyst_types_all": ["government_contract"],
            },
            "research_scorecard": {"structured_confirmation_count": 1, "notes": ["structured"]},
        },
        {
            "ticker": "INFQ",
            "research_priority_score": 8.4,
            "hyper_trade_score": 8.8,
            "lane_tags": ["SOCIAL_TAPE_ROCKET"],
            "cluster": {
                "primary_ticker": "INFQ",
                "claim_summary": "INFQ quantum investor event gains attention",
                "events": [
                    {
                        "source_name": "grok_x_search",
                        "source_url": "https://example.com/infq-x",
                        "headline": "INFQ quantum investor event gains attention",
                        "published_at": "2026-05-21T12:05:00+00:00",
                        "social_flag": True,
                    }
                ],
                "structured_sources": [],
                "official_sources": [],
                "social_sources": ["https://example.com/infq-x"],
                "obscure_sources": [],
                "catalyst_types_all": ["social_acceleration"],
            },
            "research_scorecard": {"social_confirmation_count": 1, "attention_acceleration_score": 8.0, "notes": ["social"]},
        },
    ]

    merged = _merge_ranked_by_ticker(rows)

    assert [row["ticker"] for row in merged] == ["INFQ"]
    row = merged[0]
    assert len(row["cluster"]["events"]) == 2
    assert row["research_priority_score"] == 8.4
    assert row["hyper_trade_score"] == 8.8
    assert row["research_scorecard"]["structured_confirmation_count"] == 1
    assert row["research_scorecard"]["social_confirmation_count"] == 1
    assert row["research_scorecard"]["validation_status"] == "structured_confirmed"
    assert row["lane_tags"] == ["SOCIAL_TAPE_ROCKET", "VERIFIED_CATALYST_RUNNER"]


def test_research_pipeline_discovery_only_builds_dynamic_universe(tmp_path):
    pipeline = ResearchPipeline(
        cfg={"session": {"timezone": "America/New_York"}},
        workflow_cfg={"workflow": {"thresholds": {"research": {"max_candidates_after_discovery": 10, "max_candidates_for_verification": 5}, "execution": {}}}},
    )
    pipeline.storage = ResearchRunStorage(root=tmp_path / "run")
    pipeline.discovery_scouts = [
        StubScout(
            [
                {"ticker_candidates": ["MRAM"], "official_flag": False, "structured_flag": True, "social_flag": False, "freshness_hours": 0.5, "notes": [], "credibility_score_initial": 7.5},
                {"ticker_candidates": ["ABEO"], "official_flag": False, "structured_flag": False, "social_flag": True, "freshness_hours": 0.1, "notes": ["mentions=4"], "credibility_score_initial": 4.0},
            ]
        )
    ]
    pipeline.seeded_discovery_scouts = []
    pipeline.evidence_scouts = []
    result = pipeline.run_once(discovery_only=True, manual_symbols=[])
    assert result["summary"]["discovered_symbols_count"] == 2
    discovered = json.loads((tmp_path / "run" / "normalized" / "discovered_symbols.json").read_text())
    assert discovered[0] == "MRAM"


def test_research_pipeline_auto_runs_governed_deep_mini(tmp_path, monkeypatch):
    pipeline = ResearchPipeline(
        cfg={"session": {"timezone": "America/New_York"}},
        workflow_cfg={
            "workflow": {
                "thresholds": {"research": {"max_candidates_after_discovery": 10, "max_candidates_for_verification": 5}, "execution": {}},
                "deep_research": {"enabled": True, "auto_run": True, "top_n_for_deep_mini": 2},
            }
        },
    )
    pipeline.storage = ResearchRunStorage(root=tmp_path / "run")
    event = {
        "ticker_candidates": ["MRAM"],
        "source_name": "benzinga_newswire",
        "official_flag": False,
        "structured_flag": True,
        "social_flag": False,
        "freshness_hours": 0.5,
        "notes": [],
        "credibility_score_initial": 7.5,
        "catalyst_type": "product_or_partnership",
        "headline": "MRAM wins contract",
        "raw_text": "MRAM wins contract",
        "company_name": "Everspin",
        "source_url": "https://example.com/mram",
        "published_at": "2026-04-30T14:00:00+00:00",
        "updated_at": "2026-04-30T14:00:00+00:00",
        "discovered_at": "2026-04-30T14:05:00+00:00",
    }
    pipeline.discovery_scouts = [StubScout([event])]
    pipeline.seeded_discovery_scouts = []
    pipeline.evidence_scouts = [StubScout([event])]

    def fake_run(shortlist, context, output_dir, deep_cfg=None):
        return SimpleNamespace(
            prompt_path=str(output_dir / "deep_mini_shortlist_fake.txt"),
            to_dict=lambda: {
                "status": "completed",
                "success": True,
                "route_chosen": "deep_mini",
                "summary_path": str(output_dir / "summary.json"),
                "structured_packet": {"best_pick": "MRAM", "source_mode": "governed_deep_mini"},
            },
        )

    monkeypatch.setattr("src.workflows.research_pipeline.run_governed_deep_mini", fake_run)
    result = pipeline.run_once(manual_symbols=[], skip_overlays=True)
    assert result["artifacts"]["deep_mini_run"]["success"] is True
    assert result["summary"]["candidate_research_packets_count"] == 1
    assert result["artifacts"]["candidate_research_packets"].endswith("normalized/candidate_research_packets.json")
    assert result["summary"]["deep_mini_status"] == "completed"
    assert result["summary"]["execution_gate_skipped"] is True
    packets = json.loads((tmp_path / "run" / "normalized" / "candidate_research_packets.json").read_text())
    assert packets[0]["ticker"] == "MRAM"
    assert "evidence_table" in packets[0]
    packet = json.loads((tmp_path / "run" / "normalized" / "daily_best_pick_packet.json").read_text())
    assert packet["best_pick"] == "MRAM"


def test_research_pipeline_rejects_grok_d_research_as_live_primary(tmp_path):
    pipeline = ResearchPipeline(
        cfg={"session": {"timezone": "America/New_York"}},
        workflow_cfg={
            "workflow": {
                "thresholds": {"research": {"max_candidates_after_discovery": 10, "max_candidates_for_verification": 5}, "execution": {}},
                "deep_research": {"enabled": True, "auto_run": True, "mode": "grok_d_research", "require_for_live_research": True, "require_grok_for_live_research": True, "top_n_for_deep_mini": 2},
            }
        },
    )
    pipeline.storage = ResearchRunStorage(root=tmp_path / "run")
    pipeline.discovery_scouts = [StubScout([])]
    pipeline.seeded_discovery_scouts = []
    pipeline.evidence_scouts = []

    try:
        pipeline.run_once(manual_symbols=[], skip_overlays=True)
    except ValueError as exc:
        assert "invalid_deep_research_mode:grok_d_research" in str(exc)
    else:
        raise AssertionError("grok_d_research must not be accepted as the live primary selector")


def test_research_pipeline_skip_deep_mini_uses_fallback(tmp_path, monkeypatch):
    pipeline = ResearchPipeline(
        cfg={"session": {"timezone": "America/New_York"}},
        workflow_cfg={
            "workflow": {
                "thresholds": {"research": {"max_candidates_after_discovery": 10, "max_candidates_for_verification": 5}, "execution": {}},
                "deep_research": {"enabled": True, "auto_run": True, "top_n_for_deep_mini": 2},
            }
        },
    )
    pipeline.storage = ResearchRunStorage(root=tmp_path / "run")
    event = {
        "ticker_candidates": ["MRAM"],
        "source_name": "benzinga_newswire",
        "official_flag": False,
        "structured_flag": True,
        "social_flag": False,
        "freshness_hours": 0.5,
        "notes": [],
        "credibility_score_initial": 7.5,
        "catalyst_type": "product_or_partnership",
        "headline": "MRAM wins contract",
        "raw_text": "MRAM wins contract",
        "company_name": "Everspin",
        "source_url": "https://example.com/mram",
        "published_at": "2026-04-30T14:00:00+00:00",
        "updated_at": "2026-04-30T14:00:00+00:00",
        "discovered_at": "2026-04-30T14:05:00+00:00",
    }
    pipeline.discovery_scouts = [StubScout([event])]
    pipeline.seeded_discovery_scouts = []
    pipeline.evidence_scouts = [StubScout([event])]

    def fail_run(*args, **kwargs):
        raise AssertionError("deep mini should be skipped")

    monkeypatch.setattr("src.workflows.research_pipeline.run_governed_deep_mini", fail_run)
    result = pipeline.run_once(manual_symbols=[], skip_overlays=True, skip_deep_mini=True)
    assert result["artifacts"]["deep_mini_run"] is None
    packet = json.loads((tmp_path / "run" / "normalized" / "daily_best_pick_packet.json").read_text())
    assert packet["source_mode"] == "internal_fallback"


def test_research_pipeline_rejects_invalid_deep_mini_env_override(monkeypatch):
    pipeline = ResearchPipeline(cfg={}, workflow_cfg={"workflow": {"deep_research": {"enabled": True}}})
    monkeypatch.setenv("ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS", "abc")
    try:
        pipeline._deep_research_cfg()
    except ValueError as exc:
        assert "invalid_ROI_SNIPS_DEEP_MINI_TIMEOUT_SECONDS" in str(exc)
    else:
        raise AssertionError("expected invalid env override to raise clean ValueError")


def test_merge_ranked_by_ticker_consolidates_duplicate_source_events():
    rows = [
        {
            "ticker": "INFQ",
            "cluster": {
                "primary_ticker": "INFQ",
                "events": [{"source_url": "https://example.com/one", "headline": "INFQ CHIPS LOI"}],
                "official_sources": [],
                "structured_sources": ["https://example.com/one"],
                "social_sources": [],
                "obscure_sources": [],
                "catalyst_types_all": ["government_contract"],
                "first_seen_at": "2026-05-21T12:00:00+00:00",
                "latest_update_at": "2026-05-21T12:00:00+00:00",
            },
            "research_scorecard": {"structured_confirmation_count": 1, "official_confirmation_count": 0, "social_confirmation_count": 0},
            "hyper_trade_score": 8.8,
            "research_priority_score": 8.5,
        },
        {
            "ticker": "INFQ",
            "cluster": {
                "primary_ticker": "INFQ",
                "events": [{"source_url": "https://example.com/two", "headline": "INFQ quantum funding"}],
                "official_sources": ["https://example.com/two"],
                "structured_sources": [],
                "social_sources": ["https://example.com/social"],
                "obscure_sources": [],
                "catalyst_types_all": ["government_contract"],
                "first_seen_at": "2026-05-21T12:02:00+00:00",
                "latest_update_at": "2026-05-21T12:05:00+00:00",
            },
            "research_scorecard": {"structured_confirmation_count": 0, "official_confirmation_count": 1, "social_confirmation_count": 1},
            "hyper_trade_score": 8.1,
            "research_priority_score": 8.0,
        },
    ]
    merged = _merge_ranked_by_ticker(rows)
    assert len(merged) == 1
    assert len(merged[0]["cluster"]["events"]) == 2
    assert merged[0]["research_scorecard"]["validation_status"] == "primary_and_structured_confirmed"


def test_merge_ranked_by_ticker_prefers_direct_infq_claim_summary():
    rows = [
        {
            "ticker": "INFQ",
            "cluster": {
                "primary_ticker": "INFQ",
                "claim_summary": "D-Wave Vice President Sells Shares: QBTS Stock Is Trending",
                "events": [
                    {
                        "source_url": "https://example.com/qbts",
                        "headline": "D-Wave Vice President Sells Shares: QBTS Stock Is Trending",
                        "raw_text": "D-Wave shares jump on quantum funding reports.",
                        "published_at": "2026-05-22T12:00:00+00:00",
                        "structured_flag": True,
                    }
                ],
                "official_sources": [],
                "structured_sources": ["https://example.com/qbts"],
                "social_sources": [],
                "obscure_sources": [],
                "catalyst_types_all": ["government_contract"],
            },
            "research_scorecard": {"structured_confirmation_count": 1, "notes": []},
            "hyper_trade_score": 8.8,
            "research_priority_score": 8.4,
        },
        {
            "ticker": "INFQ",
            "cluster": {
                "primary_ticker": "INFQ",
                "claim_summary": "INFQ sector-theme basket candidate: quantum_computing",
                "events": [
                    {
                        "source_name": "theme_basket_scout",
                        "source_url": "https://example.com/theme",
                        "headline": "INFQ sector-theme basket candidate: quantum_computing",
                        "raw_text": "government-backed quantum winners",
                        "published_at": "2026-05-22T13:00:00+00:00",
                        "structured_flag": True,
                    }
                ],
                "official_sources": [],
                "structured_sources": ["https://example.com/theme"],
                "social_sources": [],
                "obscure_sources": [],
                "catalyst_types_all": ["sector_theme_wave"],
            },
            "research_scorecard": {"structured_confirmation_count": 1, "notes": []},
            "hyper_trade_score": 8.1,
            "research_priority_score": 8.0,
        },
        {
            "ticker": "INFQ",
            "cluster": {
                "primary_ticker": "INFQ",
                "claim_summary": "D-Wave Quantum, IBM, Infleqtion, Rigetti Computing And Walmart Are On Investors' Radars Today",
                "events": [
                    {
                        "source_url": "https://example.com/infq",
                        "headline": "D-Wave Quantum, IBM, Infleqtion, Rigetti Computing And Walmart Are On Investors' Radars Today",
                        "raw_text": "Infleqtion is part of the government-backed quantum sector basket.",
                        "published_at": "2026-05-22T11:00:00+00:00",
                        "structured_flag": True,
                    }
                ],
                "official_sources": [],
                "structured_sources": ["https://example.com/infq"],
                "social_sources": [],
                "obscure_sources": [],
                "catalyst_types_all": ["government_contract"],
            },
            "research_scorecard": {"structured_confirmation_count": 1, "notes": []},
            "hyper_trade_score": 7.9,
            "research_priority_score": 7.8,
        },
    ]

    merged = _merge_ranked_by_ticker(rows)

    assert merged[0]["cluster"]["claim_summary"] == "D-Wave Quantum, IBM, Infleqtion, Rigetti Computing And Walmart Are On Investors' Radars Today"
