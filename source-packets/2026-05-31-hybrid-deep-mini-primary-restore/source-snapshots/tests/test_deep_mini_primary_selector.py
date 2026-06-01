import pytest

from src.workflows.research_pipeline import ResearchPipeline


def test_research_pipeline_rejects_grok_d_research_live_mode():
    pipeline = ResearchPipeline(
        cfg={"research_mode": {"deep_mini_required_for_live_research": True}},
        workflow_cfg={"workflow": {"deep_research": {"enabled": True, "mode": "grok_d_research", "require_for_live_research": True}}},
    )
    pipeline.discovery_scouts = []
    pipeline.seeded_discovery_scouts = []
    pipeline.evidence_scouts = []

    with pytest.raises(ValueError, match="invalid_deep_research_mode:grok_d_research"):
        pipeline.run_once(skip_overlays=True)
