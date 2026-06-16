from src.research.cluster import cluster_events


def test_cluster_events_groups_by_ticker_and_claim_and_derives_scores():
    events = [
        {
            "ticker_candidates": ["AAPL"],
            "source_name": "sec_edgar",
            "catalyst_type": "product_or_partnership",
            "headline": "Apple launches new product",
            "raw_text": "Apple launches new product today",
            "company_name": "Apple",
            "source_url": "https://example.com/1",
            "official_flag": True,
            "structured_flag": False,
            "social_flag": False,
            "credibility_score_initial": 9.0,
            "freshness_hours": 1.0,
            "published_at": "2026-04-15T10:00:00+00:00",
            "discovered_at": "2026-04-15T10:00:00+00:00",
            "updated_at": "2026-04-15T10:00:00+00:00",
        },
        {
            "ticker_candidates": ["AAPL"],
            "source_name": "benzinga_newswire",
            "catalyst_type": "product_or_partnership",
            "headline": "Apple launches new product",
            "raw_text": "Apple launches new product today",
            "company_name": "Apple",
            "source_url": "https://example.com/2",
            "official_flag": False,
            "structured_flag": True,
            "social_flag": False,
            "credibility_score_initial": 7.0,
            "freshness_hours": 0.5,
            "published_at": "2026-04-15T10:30:00+00:00",
            "discovered_at": "2026-04-15T10:30:00+00:00",
            "updated_at": "2026-04-15T10:30:00+00:00",
        },
    ]
    clusters = cluster_events(events)
    assert len(clusters) == 1
    assert clusters[0].primary_ticker == "AAPL"
    assert clusters[0].official_confirmed
    assert clusters[0].official_confirmation_count == 1
    assert clusters[0].structured_confirmation_count == 1
    assert clusters[0].catalyst_strength_score > 0
    assert clusters[0].research_priority_score > 0


def test_cluster_events_detects_exhaustion_and_penalizes_story_stage():
    events = [
        {
            "ticker_candidates": ["ABEO"],
            "source_name": "reddit",
            "catalyst_type": "social_acceleration",
            "headline": "ABEO extends gains after rally and squeeze",
            "raw_text": "ABEO extends gains after rally and squeeze",
            "company_name": "ABEO",
            "source_url": "https://example.com/reddit",
            "official_flag": False,
            "structured_flag": False,
            "social_flag": True,
            "credibility_score_initial": 4.0,
            "freshness_hours": 0.2,
            "published_at": "2026-04-15T10:30:00+00:00",
            "discovered_at": "2026-04-15T10:30:00+00:00",
            "updated_at": "2026-04-15T10:30:00+00:00",
            "notes": ["mentions=14", "gap_pct=28.0", "premarket_dollar_volume=6500000"],
        }
    ]
    clusters = cluster_events(events)
    assert len(clusters) == 1
    assert clusters[0].crowdedness_preliminary >= 3.0
    assert clusters[0].story_stage_score <= 3.0
    assert clusters[0].asymmetry_score < 6.0


def test_cluster_events_boosts_hard_biotech_catalyst_strength():
    events = [
        {
            "ticker_candidates": ["ABEO"],
            "source_name": "fda_scout",
            "catalyst_type": "medical_or_biotech",
            "headline": "ABEO receives FDA fast track designation",
            "raw_text": "ABEO receives FDA fast track designation",
            "company_name": "ABEO",
            "source_url": "https://example.com/fda",
            "official_flag": False,
            "structured_flag": True,
            "social_flag": False,
            "credibility_score_initial": 7.4,
            "freshness_hours": 0.3,
            "published_at": "2026-04-15T10:30:00+00:00",
            "discovered_at": "2026-04-15T10:30:00+00:00",
            "updated_at": "2026-04-15T10:30:00+00:00",
        }
    ]
    clusters = cluster_events(events)
    assert len(clusters) == 1
    assert clusters[0].catalyst_strength_score >= 4.0
