from src.workflows.deep_mini_bridge import build_deep_mini_brief, repo_root, write_deep_mini_input
from tests.runbook_helpers import ranked_row


PROMPTS = [
    "16_DEEP_MINI_BROAD_PRO_STYLE_STOCK_HUNT.md",
    "17_DEEP_MINI_SHORTLIST_BEST_IDEA.md",
    "18_DEEP_MINI_ADVERSARIAL_RED_TEAM.md",
    "19_DEEP_MINI_FINAL_PACKET_SCHEMA.md",
]


def test_deep_mini_prompts_embed_charles_stock_hunt_mandate() -> None:
    prompt_dir = repo_root() / "docs" / "prompts" / "rebuild"
    combined = "\n".join((prompt_dir / name).read_text() for name in PROMPTS)

    for name in PROMPTS:
        assert (prompt_dir / name).exists()
    for phrase in [
        "Charles is looking to make a stock investment today just after market open",
        "Treat this as if Charles is consulting one of the best stock pickers in the world",
        "Do not produce a generic watchlist",
        "Identify the single best short-term stock opportunity",
        "Do deep research, think carefully, and synthesize both institutional-quality signals and retail sentiment",
        "Charles is completely fine with high risk",
        "FDA approvals",
        "government contracts",
        "CHIPS/DoD/DOE/NASA/SAM.gov/USAspending catalysts",
        "50-150 possible explosive",
        "company press releases",
        "SEC filings",
        "Reddit",
        "StockTwits",
        "X/Grok",
        "float",
        "short-interest",
        "one decisive stock",
        "same-day target",
        "1-3 day target",
        "thesis break",
        "profit-taking triggers",
        "danger signals",
        "Do not default to NVDA, AMD, AAPL, AMZN, META, TSLA, MSFT, GOOGL, PLTR, SPY, or QQQ",
        "deterministic fallback cannot be executable for live",
    ]:
        assert phrase in combined


def test_generated_shortlist_input_embeds_charles_full_mandate() -> None:
    brief = build_deep_mini_brief([ranked_row("ABCD")], {"generated_at_utc": "2026-05-29T12:00:00+00:00"})

    for phrase in [
        "Charles stock-picking mandate:",
        "Charles is looking to make a stock investment today just after market open",
        "Conduct exhaustive, high-depth research across all relevant resources available",
        "Treat this as if Charles is consulting one of the best stock pickers in the world",
        "Do not produce a generic watchlist",
        "Identify the single best short-term stock opportunity for today",
        "Do deep research, think carefully, and synthesize both institutional-quality signals and retail sentiment",
        "Charles is completely fine with high risk",
        "opening burst, gap-and-go, premarket-high reclaim, VWAP reclaim, ORB break",
        "same-style volatile backups",
        "why mega-cap defaults were rejected",
        "Do not recycle INFQ or any stale prior winner",
        "If the only choices are stale prior winners or mega-cap filler, return NO_TRADE_RESEARCH_INCOMPLETE",
        "deterministic fallback cannot be executable for live",
    ]:
        assert phrase in brief


def test_write_deep_mini_input_also_writes_canonical_shortlist_input_md(tmp_path) -> None:
    timestamped = write_deep_mini_input([ranked_row("ABCD")], {"generated_at_utc": "2026-05-29T12:00:00+00:00"}, tmp_path)
    canonical = tmp_path / "shortlist_input.md"

    assert timestamped.exists()
    assert canonical.exists()
    assert canonical.read_text() == timestamped.read_text()
    assert "Charles is looking to make a stock investment today just after market open" in canonical.read_text()
    assert "Treat this as if Charles is consulting one of the best stock pickers in the world" in canonical.read_text()
