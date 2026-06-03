from src.research.universe import derive_candidate_universe


def test_derive_candidate_universe_prefers_confirmed_symbols():
    events = [
        {"ticker_candidates": ["ABCD"], "official_flag": True, "structured_flag": False, "social_flag": False, "freshness_hours": 0.5, "notes": [], "credibility_score_initial": 9.0},
        {"ticker_candidates": ["EFGH"], "official_flag": False, "structured_flag": True, "social_flag": True, "freshness_hours": 0.2, "notes": ["mentions=5"], "credibility_score_initial": 6.5},
        {"ticker_candidates": ["ABCD"], "official_flag": False, "structured_flag": True, "social_flag": False, "freshness_hours": 1.0, "notes": [], "credibility_score_initial": 7.0},
    ]
    ranked = derive_candidate_universe(events)
    assert ranked[0] == "ABCD"
    assert "EFGH" in ranked


def test_derive_candidate_universe_penalizes_megacap_defaults_when_evidence_is_similar():
    events = [
        {"ticker_candidates": ["NVDA"], "official_flag": False, "structured_flag": True, "social_flag": False, "freshness_hours": 0.4, "notes": [], "credibility_score_initial": 7.0, "catalyst_type": "product_or_partnership", "source_name": "benzinga_newswire"},
        {"ticker_candidates": ["MRAM"], "official_flag": False, "structured_flag": True, "social_flag": False, "freshness_hours": 0.5, "notes": ["lesser_known_candidate"], "credibility_score_initial": 6.9, "catalyst_type": "obscure_catalyst_candidate", "source_name": "obscure_scout"},
    ]
    ranked = derive_candidate_universe(events)
    assert ranked[0] == "MRAM"
