from src.research.strategy_fit import same_style_backup_status


def test_same_style_backup_failure_blocks_optimized_success() -> None:
    primary = {"ticker": "ABCD", "lane_tags": ["fresh_fda"], "asymmetry_score": 9, "freshness_score": 9, "momentum_score": 9}
    backups = [{"ticker": "NVDA", "lane_tags": ["ai_mega_cap"], "market_cap_bucket": "mega", "asymmetry_score": 3, "freshness_score": 9, "momentum_score": 9}]

    status = same_style_backup_status(primary, backups)

    assert status["status"] == "DEGRADED"
    assert status["same_style_backup_pool_ok"] is False
