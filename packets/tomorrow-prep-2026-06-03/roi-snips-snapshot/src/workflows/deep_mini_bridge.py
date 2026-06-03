from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..common.config import repo_root
from ..research.models import DailyBestPickPacket

DEEP_MINI_REQUIRED_BLOCKER = "deep_mini_required_for_live_research_not_completed"
DEEP_MINI_REQUIRED_ARTIFACTS = [
    "broad_discovery_input.md",
    "broad_discovery_summary.json",
    "broad_discovery_raw_output.txt",
    "shortlist_input.md",
    "shortlist_synthesis_summary.json",
    "shortlist_raw_output.txt",
    "red_team_summary.json",
    "final_packet.json",
]

CHARLES_SHORTLIST_STOCK_PICKING_MANDATE = """
Charles is looking to make a stock investment today just after market open, with the intention of selling the same day or within a couple of days. Conduct exhaustive, high-depth research across all relevant resources available, including financial news, company press releases, SEC filings, earnings materials, analyst commentary, trading blogs, market newsletters, Reddit threads, StockTwits, X/Grok sentiment, stock forums, Motley Fool-style market commentary, and any other credible or high-signal sources. Treat this as if Charles is consulting one of the best stock pickers in the world for a high-conviction short-term trade.

Do not produce a generic watchlist. Identify the single best short-term stock opportunity for today based on the strongest combination of catalyst, sentiment, technical setup, and probability of a sharp near-term move. This means one decisive stock, not a broad list. Do deep research, think carefully, and synthesize both institutional-quality signals and retail sentiment.

Focus on volatile stocks with credible potential for a major short-term revaluation due to a concrete catalyst. This may include FDA approvals, medical device clearance, trial data, product launches, mergers, acquisitions, strategic reviews, partnerships, licensing deals, government contracts, contract awards, CHIPS/DoD/DOE/NASA/SAM.gov/USAspending catalysts, earnings surprises, guidance revisions, legal/regulatory developments, short squeeze potential, unusual volume, sector momentum, social attention acceleration, analyst upgrades, same-day investor events, or other material triggers.

Charles is completely fine with high risk for this small investment and can tolerate maximum risk. Prioritize asymmetric upside and high-conviction setups over safer, lower-volatility names. Charles cares more about explosive short-term potential than stability.

Do not ignore hype if hype is clearly becoming a market-moving force, but do not treat hype as source validation. Hype plus catalyst plus premarket volume plus live tape may validate a momentum trade.

Weigh:
- current news flow and catalyst strength
- official, structured, and social evidence
- sentiment across retail and professional channels
- premarket or early-session trading behavior
- unusual volume, momentum, float, and short-interest if available
- technical levels such as support, resistance, breakout levels, gap fills, VWAP, premarket high/low, and likely liquidity zones
- whether the move is already overcrowded or still early
- what could invalidate the trade quickly
- what exact strategy fits the setup: opening burst, gap-and-go, premarket-high reclaim, VWAP reclaim, ORB break, second-leg continuation, event-timed catalyst reaction, or no trade

Final output must choose one best idea or explicitly no-trade. It must include:
1. single best stock to buy today, or no-trade
2. ticker and company
3. exact reason it could move sharply in the next hours or days
4. underlying catalyst and why the market may not have fully priced it in
5. evidence reviewed, split into official / structured / social / market-data evidence
6. sentiment and discussion trend
7. premarket or current tape behavior
8. suggested limit buy price, buy range, or wait condition
9. realistic same-day upside target
10. realistic 1-3 day upside target
11. downside level or clear thesis-break threshold
12. monitoring timeframes after entry
13. specific sell triggers, including profit-taking and danger signals
14. chosen strategy
15. same-style volatile backups
16. why backups lost
17. why mega-cap defaults were rejected
18. stale prior-winner check
19. source breadth status
20. confidence
21. must-not-trade conditions

Hard restrictions:
- Do not default to NVDA, AMD, AAPL, AMZN, META, TSLA, MSFT, GOOGL, PLTR, SPY, or QQQ unless the catalyst and tape are truly exceptional.
- Do not recycle INFQ or any stale prior winner unless there is a fresh catalyst today or live-tape continuation confirmation.
- If the only choices are stale prior winners or mega-cap filler, return NO_TRADE_RESEARCH_INCOMPLETE.
- If deep-mini output is missing, timed out, failed, or unparsed, deterministic fallback cannot be executable for live.
""".strip()


@dataclass
class DeepMiniRunArtifacts:
    status: str
    success: bool
    prompt_path: str | None = None
    summary_path: str | None = None
    executor_output_path: str | None = None
    structured_packet_path: str | None = None
    structured_packet: dict[str, Any] | None = None
    route_chosen: str | None = None
    error: str | None = None
    runner_stdout: str | None = None
    runner_stderr: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def workspace_root() -> Path:
    return repo_root().parent


def default_deep_research_runner() -> Path:
    return workspace_root() / "tools" / "deep-research-runner"


def env_truthy(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def deep_mini_required_for_live_research(deep_cfg: dict[str, Any] | None = None, research_mode: dict[str, Any] | None = None) -> bool:
    deep_cfg = deep_cfg or {}
    research_mode = research_mode or {}
    if env_truthy("ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH"):
        return True
    if research_mode.get("deep_mini_required_for_live_research") is True:
        return True
    if deep_cfg.get("require_for_live_research") is True and env_truthy("ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION"):
        return True
    return False


def deep_mini_artifact_paths(run_root: Path) -> dict[str, str]:
    deep_dir = run_root / "deep_mini"
    return {name: str(deep_dir / name) for name in DEEP_MINI_REQUIRED_ARTIFACTS}


def deep_mini_artifact_status(run_root: Path) -> dict[str, Any]:
    paths = deep_mini_artifact_paths(run_root)
    missing = [path for path in paths.values() if not Path(path).exists()]
    broad = _read_summary(Path(paths["broad_discovery_summary.json"]))
    shortlist = _read_summary(Path(paths["shortlist_synthesis_summary.json"]))
    red_team = _read_summary(Path(paths["red_team_summary.json"]))
    final_packet = _read_summary(Path(paths["final_packet.json"]))
    return {
        "required": True,
        "paths": paths,
        "missing": missing,
        "broad_status": broad.get("status"),
        "shortlist_status": shortlist.get("status"),
        "red_team_status": red_team.get("red_team_status") or red_team.get("status"),
        "final_status": final_packet.get("status"),
        "completed": (
            not missing
            and broad.get("status") == "completed"
            and shortlist.get("status") == "completed"
            and (red_team.get("red_team_status") or red_team.get("status")) in {"PASS", "PASS_ONLY_WITH_TAPE", "completed"}
            and final_packet.get("status") not in {None, "", "NO_TRADE_RESEARCH_INCOMPLETE"}
        ),
    }


def _summarize_row_for_prompt(row: dict[str, Any]) -> dict[str, Any]:
    cluster = row.get("cluster") or {}
    scorecard = row.get("research_scorecard") or {}
    overlay = row.get("overlay") or {}
    gate = row.get("execution_gate") or {}
    return {
        "ticker": row.get("ticker") or cluster.get("primary_ticker"),
        "company_name": cluster.get("company_name"),
        "catalyst_type": cluster.get("catalyst_type_primary"),
        "claim_summary": cluster.get("claim_summary"),
        "research_priority_score": row.get("research_priority_score"),
        "story_stage": row.get("story_stage") or scorecard.get("story_stage"),
        "catalyst_strength_score": scorecard.get("catalyst_strength_score"),
        "freshness_score": scorecard.get("freshness_score"),
        "attention_acceleration_score": scorecard.get("attention_acceleration_score"),
        "crowding_score": scorecard.get("crowding_score"),
        "asymmetry_score": scorecard.get("asymmetry_score"),
        "official_confirmation_count": scorecard.get("official_confirmation_count"),
        "structured_confirmation_count": scorecard.get("structured_confirmation_count"),
        "social_confirmation_count": scorecard.get("social_confirmation_count"),
        "validation_status": scorecard.get("validation_status"),
        "scorecard_notes": (scorecard.get("notes") or [])[:8],
        "official_sources": (cluster.get("official_sources") or [])[:4],
        "structured_sources": (cluster.get("structured_sources") or [])[:4],
        "social_sources": (cluster.get("social_sources") or [])[:4],
        "overlay": {
            "last_premarket_price": overlay.get("last_premarket_price"),
            "gap_pct": overlay.get("gap_pct"),
            "premarket_dollar_volume": overlay.get("premarket_dollar_volume"),
            "estimated_spread_pct": overlay.get("estimated_spread_pct"),
            "execution_readiness_score": overlay.get("execution_readiness_score"),
            "execution_blockers": (overlay.get("execution_blockers") or [])[:5],
            "execution_warnings": (overlay.get("execution_warnings") or [])[:5],
        },
        "execution_gate": {
            "passed": gate.get("passed"),
            "execution_readiness_score": gate.get("execution_readiness_score"),
            "blockers": (gate.get("blockers") or [])[:5],
            "warnings": (gate.get("warnings") or [])[:5],
        },
    }


def _summarize_context_for_prompt(context: dict[str, Any]) -> dict[str, Any]:
    payload = dict(context or {})
    execution_eligible = payload.pop("execution_eligible", None) or []
    payload["execution_eligible_tickers"] = [
        str(row.get("ticker") or ((row.get("cluster") or {}).get("primary_ticker") or "")).upper()
        for row in execution_eligible[:8]
        if str(row.get("ticker") or ((row.get("cluster") or {}).get("primary_ticker") or "")).strip()
    ]
    payload["execution_eligible_count"] = payload.get("execution_eligible_count", len(execution_eligible))
    return payload


def load_grok_social_context(run_root: Path) -> dict[str, Any]:
    grok_dir = run_root / "grok"
    artifact_names = [
        "x_heat_radar.json",
        "web_verification.json",
        "x_threads.json",
        "social_velocity_summary.json",
        "challenger_notes.json",
        "ticket_input_summary.json",
        "candidate_discovery_tournament.json",
    ]
    artifacts: dict[str, Any] = {}
    missing: list[str] = []
    for name in artifact_names:
        path = grok_dir / name
        if not path.exists():
            missing.append(str(path))
            continue
        try:
            artifacts[name] = json.loads(path.read_text())
        except Exception as exc:
            artifacts[name] = {"status": "unreadable", "error": str(exc), "path": str(path)}
    return {
        "stage": "grok_social_heat_context",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_role": "Grok/X is a social heat discovery and challenger lane only; it cannot authorize a live ticket.",
        "can_authorize_live_trade": False,
        "missing_artifacts": missing,
        "artifacts": artifacts,
    }


def _render_grok_context_for_prompt(context: dict[str, Any]) -> str:
    grok_context = context.get("grok_social_context") or {}
    if not isinstance(grok_context, dict) or not grok_context:
        return "Grok/X Heat Radar: no Grok social heat artifacts were supplied; continue with deep-mini as primary selector."
    return "\n".join(
        [
            "Grok/X Heat Radar and Web Verification Context:",
            "",
            "Role: treat Grok output as social heat, narrative discovery, fast web verification, and challenger notes. It is not proof by itself and cannot authorize a live trade.",
            "",
            "Deep-mini must judge whether Grok-discovered names are tradable, unverified, already crowded, pump-only, useful discovery but bad entry, or worthy of a ticket.",
            "",
            "Grok context JSON:",
            json.dumps(grok_context, indent=2, sort_keys=True)[:60000],
        ]
    )


def build_deep_mini_brief(shortlist: list[dict[str, Any]], context: dict[str, Any] | None = None) -> str:
    context = context or {}
    shortlist_summary = [_summarize_row_for_prompt(row) for row in shortlist[:5]]
    context_summary = _summarize_context_for_prompt(context)
    return "\n".join(
        [
            "You are doing a governed deep-mini research pass for Roi Snips.",
            "",
            "Objective:",
            "Identify the single best long-only U.S. stock or ETF opportunity from a dynamically discovered shortlist for an entry between 09:30 and 11:00 ET, including opening-drive candidates in the first five minutes, and a same-day or 1-3 day hold horizon.",
            "",
            "Primary question:",
            "Which shortlist candidate has the strongest combination of fresh catalyst, evidence quality, attention acceleration, realistic tradeability, and asymmetric near-term upside without already being obviously crowded or fully spent?",
            "",
            "Decision to be made:",
            "Choose one decisive best pick from the supplied shortlist for tomorrow's live 09:30-11:00 ET trade window, plus ranked backups and clear no-trade/invalidation reasons. This research may influence selection only; deterministic broker/risk/tape guards still control execution.",
            "",
            "Charles stock-picking mandate:",
            CHARLES_SHORTLIST_STOCK_PICKING_MANDATE,
            "",
            "Sub-questions to answer:",
            "- Which candidate has the freshest and hardest catalyst?",
            "- Which candidate has the strongest official/structured evidence stack?",
            "- Which candidate still appears early rather than exhausted or over-owned?",
            "- Which candidate offers the best realistic same-day or 1-3 day upside versus invalidation risk?",
            "",
            "Known context:",
            "- Roi Snips is long-only U.S. equities/ETFs only",
            "- No shorting, no options, no margin",
            "- One open position max",
            "- Entries only 09:30-11:00 ET",
            "- Opening-drive entries are allowed 09:30-09:34:59 ET only when sampled sub-minute or first-minute structure, plus spread and chase guards, pass",
            "- Legacy continuation entries still use ORB_BREAK and VWAP_RECLAIM after 09:35 ET",
            "- Flat by 15:45 ET if used intraday",
            "- Prefer volatile small/mid-cap or lesser-known catalyst names over conservative mega-cap defaults unless a large-cap catalyst is unusually strong",
            "- Favor fresh hard catalysts, attention acceleration, unusual volume, float scarcity, and still-early stories",
            "- Penalize crowded or purely social-only stories unless hard evidence confirms the move",
            "- Treat this as research and selection support, not an order request",
            "",
            "Assumptions to verify:",
            "- The catalyst is real, current, and materially relevant to the issuer",
            "- The move is not only recycled attention from a stale prior winner",
            "- The candidate is not merely a generic mega-cap safety fallback",
            "- The market has not already fully priced or exhausted the move before the open",
            "- Reported news, filings, social attention, and market-data context match the same ticker/security",
            "",
            "Scope boundaries:",
            "- Work only from the shortlisted U.S. stock/ETF candidates and the supplied context",
            "- Synthesize catalyst quality, evidence strength, likely crowding, execution risk, and near-term upside",
            "- Produce one decisive best pick plus ranked backups",
            "",
            "Out of scope:",
            "- Do not widen the universe beyond the provided shortlist",
            "- Do not propose shorts, options, margin trades, or non-U.S. instruments",
            "- Do not assume live order placement or override deterministic execution guards",
            "",
            "Source priorities:",
            "1. Official/company/SEC/earnings evidence already reflected in the shortlist",
            "2. Structured news / market-data confirmation already reflected in the shortlist",
            "3. Grok/X heat, social, or attention-acceleration signals only as supporting evidence",
            "",
            _render_grok_context_for_prompt(context),
            "",
            "Search plan:",
            "- For each shortlisted ticker, verify the latest official/company/SEC source behind the claimed catalyst",
            "- Cross-check structured news for timing, materiality, and whether the catalyst is already broadly repeated",
            "- Check social/retail attention only to judge acceleration, crowding, and danger signals",
            "- Compare candidates directly on catalyst freshness, asymmetry, crowding, and execution risk",
            "- Do not spend time discovering unrelated tickers outside the shortlist",
            "",
            "Required deliverable:",
            "Return:",
            "1. Executive summary",
            "2. Best pick",
            "3. Ranked backups",
            "4. Why the best pick wins over the others",
            "5. Key invalidation / no-trade risks",
            "",
            "For each final candidate include:",
            "- ticker and company name",
            "- underlying catalyst and why it could move sharply in the next hours or days",
            "- why the move may still be early vs already crowded",
            "- evidence reviewed, including official/structured/sentiment hints from the shortlist",
            "- suggested buy zone or entry framework",
            "- realistic upside target for same-day and 1-3 day horizons",
            "- downside / thesis-break level",
            "- monitoring timeframe, profit-taking triggers, danger signals, and execution risk",
            "",
            "Evidence requirements:",
            "- Prefer primary sources, official filings/releases, exchange or broker market-data context, and named structured news over unattributed chatter",
            "- Distinguish confirmed facts from inference",
            "- Cite or name the source class for each material claim",
            "- Flag contradictory evidence, dilution/offering risk, halt risk, stale catalyst risk, and excessive spread/liquidity risk",
            "",
            "Decision criteria:",
            "- Freshness and strength of catalyst",
            "- Quality of evidence over hype",
            "- Attention acceleration and asymmetric upside",
            "- Opening-bell continuation readiness when the move is real",
            "- Whether the setup still looks early rather than exhausted",
            "- Execution practicality for a retail-style trader with basic tools",
            "",
            "Stopping condition:",
            "Stop when you can confidently choose one best idea and rank the backups from the supplied shortlist/context without needing to widen the universe.",
            "",
            "Budget discipline note:",
            "This is a bounded deep-mini shortlist synthesis, not an unconstrained universe hunt. Stay focused on the provided shortlist and context.",
            "",
            "Current context JSON:",
            json.dumps(context_summary, indent=2, sort_keys=True),
            "",
            "Shortlist JSON:",
            json.dumps(shortlist_summary, indent=2, sort_keys=True),
        ]
    )


def write_deep_mini_input(shortlist: list[dict[str, Any]], context: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}_{time.time_ns()}_{uuid.uuid4().hex[:8]}"
    brief = build_deep_mini_brief(shortlist, context)
    (output_dir / "shortlist_input.md").write_text(brief)
    path = output_dir / f"deep_mini_shortlist_{run_id}.txt"
    path.write_text(brief)
    return path


def write_required_deep_mini_artifacts(
    run_root: Path,
    *,
    trading_date: str,
    broad_candidates: list[dict[str, Any]] | None,
    shortlist: list[dict[str, Any]],
    context: dict[str, Any] | None,
    deep_mini_run: dict[str, Any] | None,
    final_packet: dict[str, Any] | None,
    incomplete_reason: str | None = None,
) -> dict[str, Any]:
    deep_dir = run_root / "deep_mini"
    deep_dir.mkdir(parents=True, exist_ok=True)
    context = context or {}
    broad_candidates = broad_candidates or []
    deep_mini_run = deep_mini_run or {}
    final_packet = final_packet or {}

    broad_input = "\n".join(
        [
            "# Deep-Mini Broad Pro-Style Stock Hunt Input",
            "",
            f"Date: {trading_date}",
            "",
            "Goal: find 50-150 possible explosive short-term long candidates before final selection.",
            "",
            "Seed candidates JSON:",
            json.dumps(broad_candidates[:150], indent=2, sort_keys=True),
        ]
    )
    shortlist_input = build_deep_mini_brief(shortlist, context)
    broad_status = "completed" if not incomplete_reason and deep_mini_run.get("success") else "failed"
    shortlist_status = "completed" if not incomplete_reason and deep_mini_run.get("structured_packet") else "failed"
    red_team_status = "PASS_ONLY_WITH_TAPE" if shortlist_status == "completed" else "FAIL_NO_TRADE"

    artifacts = {
        "broad_discovery_input.md": broad_input,
        "broad_discovery_summary.json": {
            "deep_mini_stage": "broad_pro_style_discovery",
            "status": broad_status,
            "candidate_count": len(broad_candidates),
            "candidates": broad_candidates[:150],
            "notes": incomplete_reason or "Deep-mini broad discovery completed or was represented by the governed deep-mini run output.",
        },
        "broad_discovery_raw_output.txt": str(deep_mini_run.get("runner_stdout") or deep_mini_run.get("error") or incomplete_reason or ""),
        "shortlist_input.md": shortlist_input,
        "shortlist_synthesis_summary.json": {
            "deep_mini_stage": "shortlist_best_idea",
            "status": shortlist_status,
            "research_leader": final_packet.get("research_leader"),
            "executable_primary": final_packet.get("best_pick"),
            "buy_now_allowed": bool(final_packet.get("best_pick")) and shortlist_status == "completed",
            "current_action": "WAIT_OPENING_BURST" if final_packet.get("best_pick") and shortlist_status == "completed" else "NO_TRADE_RESEARCH_INCOMPLETE",
            "blocker": incomplete_reason,
            "ticker": final_packet.get("best_pick"),
            "buy_range_or_wait_condition": final_packet.get("suggested_buy_zone"),
            "same_day_target": final_packet.get("same_day_upside_target"),
            "one_to_three_day_target": final_packet.get("one_to_three_day_upside_target"),
            "thesis_break_level": final_packet.get("thesis_break_level"),
            "profit_taking_triggers": final_packet.get("profit_taking_triggers") or [],
            "danger_signals": final_packet.get("danger_signals") or [],
            "same_style_backups": final_packet.get("ranked_backups") or [],
        },
        "shortlist_raw_output.txt": str(deep_mini_run.get("runner_stdout") or deep_mini_run.get("error") or incomplete_reason or ""),
        "red_team_summary.json": {
            "red_team_status": red_team_status,
            "fatal_flaws": [incomplete_reason] if incomplete_reason else [],
            "nonfatal_risks": [],
            "entry_conditions_required": ["deterministic tape and risk gates must still pass"],
            "should_demote": bool(incomplete_reason),
            "should_block_live_trade": bool(incomplete_reason),
            "reason": incomplete_reason or "No fatal deep-mini research flaw recorded; deterministic execution remains authoritative.",
        },
        "final_packet.json": {
            **final_packet,
            "status": "NO_TRADE_RESEARCH_INCOMPLETE" if incomplete_reason else final_packet.get("status", "completed"),
            "blocker": incomplete_reason,
            "deep_mini_required_for_live_research": True,
            "deep_mini_artifact_paths": deep_mini_artifact_paths(run_root),
            "live_execution_readiness_gate_status": "BLOCKED" if incomplete_reason else "RESEARCH_COMPLETE_TAPE_GATES_STILL_REQUIRED",
        },
    }
    for filename, payload in artifacts.items():
        path = deep_dir / filename
        if filename.endswith(".json"):
            path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        else:
            path.write_text(str(payload))
    return deep_mini_artifact_status(run_root)


def _read_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _section(text: str, names: list[str]) -> str:
    if not text.strip():
        return ""
    normalized_names = [re.escape(name) for name in names]
    heading_pattern = re.compile(rf"(?im)^\s*#+\s*(?:{'|'.join(normalized_names)})\s*:?[ \t]*(.*)$")
    next_heading_pattern = re.compile(r"(?im)^\s*#+\s+.+$")
    for match in heading_pattern.finditer(text):
        start = match.end()
        inline = (match.group(1) or "").strip()
        next_heading = next_heading_pattern.search(text, start)
        end = next_heading.start() if next_heading else len(text)
        body = text[start:end].strip()
        if inline and body:
            return f"{inline}\n{body}".strip()
        return inline or body
    return ""


def _extract_best_pick_symbol(text: str) -> str | None:
    patterns = [
        r"(?im)^\s*#+\s*Best pick\s*:\s*([A-Z]{1,5})\b",
        r"(?im)^\s*Best pick\s*:\s*([A-Z]{1,5})\b",
        r"(?im)^\s*\*\*Best pick\*\*\s*:\s*([A-Z]{1,5})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).upper()
    return None


def _extract_bullet_lines(section_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^[-*]\s+", line) or re.match(r"^\d+[.)]\s+", line):
            lines.append(re.sub(r"^[-*]\s+|^\d+[.)]\s+", "", line).strip())
    return lines


def _extract_ranked_backups(section_text: str) -> list[dict[str, Any]]:
    backups: list[dict[str, Any]] = []
    for line in _extract_bullet_lines(section_text):
        match = re.search(r"\b([A-Z]{1,5})\b", line)
        if not match:
            continue
        backups.append({"ticker": match.group(1).upper(), "summary": line})
    return backups


def _extract_label_value(text: str, labels: list[str]) -> str | None:
    if not text.strip():
        return None
    alternatives = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"(?im)^\s*(?:[-*]\s*)?(?:{alternatives})\s*:?\s+(.+?)\s*$")
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _symbol_for_row(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    symbol = str(row.get("ticker") or ((row.get("cluster") or {}).get("primary_ticker") or "")).upper().strip()
    return symbol or None


def _best_row_for_symbol(symbol: str | None, shortlist: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not symbol:
        return None
    for row in shortlist:
        row_symbol = str(_symbol_for_row(row) or "")
        if row_symbol == symbol.upper():
            return row
    return None


def _fallback_trade_framework(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "why_market_may_not_be_fully_priced": None,
            "suggested_buy_zone": None,
            "same_day_upside_target": None,
            "one_to_three_day_upside_target": None,
            "thesis_break_level": None,
            "monitoring_timeframes": [],
            "profit_taking_triggers": [],
            "danger_signals": [],
        }

    symbol = _symbol_for_row(row) or "candidate"
    cluster = row.get("cluster") or {}
    scorecard = row.get("research_scorecard") or {}
    overlay = row.get("overlay") or {}
    last_price = overlay.get("last_premarket_price")
    story_stage = str(row.get("story_stage") or scorecard.get("story_stage") or "").lower()
    freshness = scorecard.get("freshness_score")
    attention = scorecard.get("attention_acceleration_score")
    crowding = scorecard.get("crowding_score")

    if isinstance(last_price, (int, float)) and last_price > 0:
        limit_high = round(float(last_price) * 1.01, 2)
        same_day_low = round(float(last_price) * 1.08, 2)
        same_day_high = round(float(last_price) * 1.18, 2)
        swing_low = round(float(last_price) * 1.15, 2)
        swing_high = round(float(last_price) * 1.35, 2)
        thesis_break = round(float(last_price) * 0.94, 2)
        suggested_buy_zone = f"Use live tape; do not chase above about ${limit_high}. Prefer VWAP/opening-range reclaim or controlled pullback near current liquidity."
        same_day_target = f"${same_day_low}-${same_day_high}, only if volume expands and spread remains controlled."
        swing_target = f"${swing_low}-${swing_high} over 1-3 days if catalyst follow-through and retail attention continue."
        thesis_break_level = f"Breaks below about ${thesis_break}, loses VWAP with fading volume, or spread/liquidity deteriorates."
    else:
        suggested_buy_zone = "No deterministic buy zone until live price, spread, and VWAP/opening-range data are available."
        same_day_target = "No deterministic same-day target until live tape is available."
        swing_target = "No deterministic 1-3 day target until live tape is available."
        thesis_break_level = "No deterministic thesis-break level until live price and VWAP/opening-range data are available."

    if story_stage == "early":
        pricing_reason = f"{symbol} screens as early: fresh evidence with attention not yet fully crowded."
    elif freshness is not None or attention is not None or crowding is not None:
        pricing_reason = f"{symbol} may not be fully priced if freshness/attention continue to improve; current scores freshness={freshness}, attention={attention}, crowding={crowding}."
    else:
        pricing_reason = f"{symbol} may not be fully priced only if the catalyst is still being discovered by market participants."

    claim = cluster.get("claim_summary")
    if claim:
        pricing_reason = f"{pricing_reason} Catalyst: {claim}"

    return {
        "why_market_may_not_be_fully_priced": pricing_reason,
        "suggested_buy_zone": suggested_buy_zone,
        "same_day_upside_target": same_day_target,
        "one_to_three_day_upside_target": swing_target,
        "thesis_break_level": thesis_break_level,
        "monitoring_timeframes": [
            "Premarket and first five minutes for spread, gap hold, and opening-drive participation.",
            "09:35-10:15 ET for VWAP reclaim, opening-range breakout, or failed follow-through.",
            "Midday only if the catalyst remains in news/social flow and price holds above key support.",
        ],
        "profit_taking_triggers": [
            "Scale or exit into a sharp volume-backed spike toward the same-day target.",
            "Take profit if the move gets vertical while social chatter becomes one-sided and spread widens.",
            "Do not turn an intraday catalyst trade into a hold unless price closes strong with continuing catalyst flow.",
        ],
        "danger_signals": [
            "VWAP loss with declining relative volume.",
            "Offering, ATM, dilution, halt, or filing that contradicts the bullish catalyst.",
            "Spread blows out or liquidity thins enough that retail execution becomes poor.",
            "Catalyst is revealed as stale, rumor-only, or already fully priced.",
        ],
    }


def _parse_deep_mini_json_output(executor_output: str) -> dict[str, Any] | None:
    raw = executor_output.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_deep_mini_output(executor_output: str, shortlist: list[dict[str, Any]], context: dict[str, Any] | None = None) -> DailyBestPickPacket:
    context = context or {}
    json_payload = _parse_deep_mini_json_output(executor_output)
    best_pick = None
    if json_payload:
        best_pick = str(
            json_payload.get("ticker")
            or json_payload.get("best_pick")
            or json_payload.get("executable_primary")
            or ""
        ).upper() or None
    if not best_pick:
        best_pick = _extract_best_pick_symbol(executor_output)
    executive_summary = _section(executor_output, ["Executive summary"])
    best_pick_section = _section(executor_output, ["Best pick", "Best pick candidate"])
    backups_section = _section(executor_output, ["Ranked backups", "Backups"])
    why_section = _section(executor_output, ["Why the best pick won over the others", "Why the best pick wins over the others"])
    invalidation_section = _section(executor_output, ["Key invalidation risks / what would make this a no-trade instead", "Key invalidation risks", "No-trade risks"])

    shortlist_symbols = {str(_symbol_for_row(row) or "").upper() for row in shortlist if _symbol_for_row(row)}
    caveats: list[str] = []
    if best_pick and shortlist_symbols and best_pick.upper() not in shortlist_symbols:
        caveats.append(f"deep_mini_best_pick_out_of_shortlist:{best_pick.upper()}")
        best_pick = None
    best_row = _best_row_for_symbol(best_pick, shortlist)
    best_pick_summary = (
        (json_payload or {}).get("exact_catalyst")
        or (json_payload or {}).get("best_pick_summary")
        or best_pick_section
        or (best_row or {}).get("claim_summary")
        or (((best_row or {}).get("cluster") or {}).get("claim_summary"))
    )
    ranked_backups = _extract_ranked_backups(backups_section)
    invalidation_risks = _extract_bullet_lines(invalidation_section)
    fallback_framework = _fallback_trade_framework(best_row)
    missing_json_fields: list[str] = []
    if json_payload is not None:
        required_json_fields = [
            "ticker",
            "exact_catalyst",
            "suggested_buy_zone",
            "same_day_upside_target",
            "one_to_three_day_upside_target",
            "thesis_break_level",
            "profit_taking_triggers",
            "danger_signals",
        ]
        missing_json_fields = [field for field in required_json_fields if not json_payload.get(field)]
        if missing_json_fields:
            caveats.append("deep_mini_json_missing_required_fields:" + ",".join(missing_json_fields))

    packet = DailyBestPickPacket(
        generated_at=str(context.get("generated_at_utc") or datetime.now(timezone.utc).isoformat()),
        best_pick=best_pick,
        shortlist=shortlist,
        execution_eligible=context.get("execution_eligible") or shortlist,
        executive_summary=executive_summary or None,
        best_pick_summary=best_pick_summary or None,
        why_best_pick_wins=why_section or None,
        ranked_backups=ranked_backups,
        key_invalidation_risks=invalidation_risks,
        source_mode="governed_deep_mini",
        route_chosen=str(context.get("route_chosen") or "deep_mini"),
        caveats=caveats if best_pick else [*caveats, "best_pick_symbol_not_parsed_from_deep_mini_output"],
        research_leader=_symbol_for_row(shortlist[0]) if shortlist else None,
        why_market_may_not_be_fully_priced=(json_payload or {}).get("why_not_fully_priced")
        or (json_payload or {}).get("why_market_may_not_be_fully_priced")
        or _extract_label_value(best_pick_section, ["Why it may not be fully priced", "Why not fully priced"])
        or fallback_framework["why_market_may_not_be_fully_priced"],
        suggested_buy_zone=(json_payload or {}).get("suggested_buy_zone")
        or (json_payload or {}).get("buy_range")
        or _extract_label_value(best_pick_section, ["Suggested buy zone", "Buy zone", "Entry"])
        or fallback_framework["suggested_buy_zone"],
        same_day_upside_target=(json_payload or {}).get("same_day_upside_target")
        or (json_payload or {}).get("same_day_target")
        or _extract_label_value(best_pick_section, ["Same-day upside target", "Same day upside target", "Same-day target"])
        or fallback_framework["same_day_upside_target"],
        one_to_three_day_upside_target=(json_payload or {}).get("one_to_three_day_upside_target")
        or (json_payload or {}).get("one_to_three_day_target")
        or _extract_label_value(best_pick_section, ["1-3 day upside target", "One-to-three-day upside target", "1-3 day target"])
        or fallback_framework["one_to_three_day_upside_target"],
        thesis_break_level=(json_payload or {}).get("thesis_break_level")
        or _extract_label_value(best_pick_section, ["Downside / thesis-break level", "Thesis-break level", "Thesis break", "Downside"])
        or fallback_framework["thesis_break_level"],
        monitoring_timeframes=(json_payload or {}).get("monitoring_timeframes")
        or _extract_bullet_lines(_section(executor_output, ["Monitoring timeframe", "Monitoring timeframes"]))
        or fallback_framework["monitoring_timeframes"],
        profit_taking_triggers=(json_payload or {}).get("profit_taking_triggers")
        or _extract_bullet_lines(_section(executor_output, ["Profit-taking triggers", "Sell triggers"]))
        or fallback_framework["profit_taking_triggers"],
        danger_signals=(json_payload or {}).get("danger_signals")
        or _extract_bullet_lines(_section(executor_output, ["Danger signals"]))
        or fallback_framework["danger_signals"],
        executable_primary=best_pick,
        buy_now_allowed=False,
        deterministic_fallback_executable_allowed=False,
    )
    return packet


def build_fallback_best_pick_packet(
    ranked: list[dict[str, Any]],
    execution_eligible: list[dict[str, Any]],
    generated_at_utc: str | None = None,
    route_chosen: str | None = None,
    caveats: list[str] | None = None,
) -> DailyBestPickPacket:
    shortlist = execution_eligible[:3] if execution_eligible else ranked[:3]
    research_leader_row = ranked[0] if ranked else None
    best_row = execution_eligible[0] if execution_eligible else None
    best_symbol = _symbol_for_row(best_row)
    best_summary = None
    if best_row:
        best_summary = (best_row.get("cluster") or {}).get("claim_summary")
    ranked_backups: list[dict[str, Any]] = []
    for row in shortlist[1:4]:
        symbol = _symbol_for_row(row) or ""
        ranked_backups.append({"ticker": symbol, "summary": (row.get("cluster") or {}).get("claim_summary")})
    packet_caveats = list(caveats or [])
    if ranked and not execution_eligible:
        packet_caveats.append("no_execution_eligible_candidate")
    framework = _fallback_trade_framework(best_row)
    return DailyBestPickPacket(
        generated_at=generated_at_utc or datetime.now(timezone.utc).isoformat(),
        best_pick=best_symbol,
        shortlist=shortlist,
        execution_eligible=execution_eligible,
        executive_summary=(
            "Fallback packet derived from internal ranking because governed deep-mini output was unavailable or unparsed."
            if best_symbol
            else "No execution-eligible best pick. Internal ranking is available for research review, but execution gates did not clear a tradeable candidate."
        ),
        best_pick_summary=best_summary,
        why_best_pick_wins=(
            "Top internal research and execution-ranked candidate based on catalyst-first scoring and late execution gating."
            if best_symbol
            else None
        ),
        ranked_backups=ranked_backups,
        key_invalidation_risks=[],
        source_mode="internal_fallback",
        route_chosen=route_chosen,
        caveats=packet_caveats,
        research_leader=_symbol_for_row(research_leader_row),
        why_market_may_not_be_fully_priced=framework["why_market_may_not_be_fully_priced"],
        suggested_buy_zone=framework["suggested_buy_zone"],
        same_day_upside_target=framework["same_day_upside_target"],
        one_to_three_day_upside_target=framework["one_to_three_day_upside_target"],
        thesis_break_level=framework["thesis_break_level"],
        monitoring_timeframes=framework["monitoring_timeframes"],
        profit_taking_triggers=framework["profit_taking_triggers"],
        danger_signals=framework["danger_signals"],
        trade_authorization={
            "authorized": False,
            "ticker": None,
            "status": "NO_TRADE_NOT_AUTHORIZED",
            "blockers": ["internal_fallback_not_executable_for_live"],
            "one_ticker_only": True,
            "deterministic_fallback_executable_allowed": False,
        },
        executable_primary=None,
        buy_now_allowed=False,
        deterministic_fallback_executable_allowed=False,
    )


def build_deep_mini_required_no_trade_packet(
    ranked: list[dict[str, Any]],
    generated_at_utc: str | None = None,
    reason: str = DEEP_MINI_REQUIRED_BLOCKER,
) -> DailyBestPickPacket:
    shortlist = ranked[:3]
    return DailyBestPickPacket(
        generated_at=generated_at_utc or datetime.now(timezone.utc).isoformat(),
        best_pick=None,
        shortlist=shortlist,
        execution_eligible=[],
        executive_summary=(
            "Live research requires governed deep-mini. Deterministic candidates may be shown for review, "
            "but they are not executable until deep-mini completes and the deterministic tape/risk gates also pass."
        ),
        best_pick_summary=None,
        why_best_pick_wins=None,
        ranked_backups=[],
        key_invalidation_risks=[reason],
        source_mode="deep_mini_required_no_trade",
        route_chosen=None,
        caveats=[reason, "deterministic_fallback_executable_allowed_false"],
        research_leader=_symbol_for_row(ranked[0]) if ranked else None,
        why_market_may_not_be_fully_priced=None,
        suggested_buy_zone=None,
        same_day_upside_target=None,
        one_to_three_day_upside_target=None,
        thesis_break_level=None,
        monitoring_timeframes=[],
        profit_taking_triggers=[],
        danger_signals=[],
        trade_authorization={
            "authorized": False,
            "ticker": None,
            "status": "NO_TRADE_NOT_AUTHORIZED",
            "blockers": [reason],
            "one_ticker_only": True,
            "deterministic_fallback_executable_allowed": False,
        },
        executable_primary=None,
        buy_now_allowed=False,
        deterministic_fallback_executable_allowed=False,
    )


def run_governed_deep_mini(
    shortlist: list[dict[str, Any]],
    context: dict[str, Any],
    output_dir: Path,
    deep_cfg: dict[str, Any] | None = None,
) -> DeepMiniRunArtifacts:
    deep_cfg = deep_cfg or {}
    prompt_path = write_deep_mini_input(shortlist, context, output_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}_{time.time_ns()}_{uuid.uuid4().hex[:8]}"
    summary_path = output_dir / f"deep_mini_governed_summary_{run_id}.json"
    executor_output_path = output_dir / f"deep_mini_governed_output_{run_id}.md"
    structured_packet_path = output_dir / f"deep_mini_governed_packet_{run_id}.json"
    runner = Path(deep_cfg.get("runner_path") or default_deep_research_runner())
    timeout_seconds = int(deep_cfg.get("timeout_seconds", 900))
    poll_seconds = int(deep_cfg.get("poll_seconds", 15))
    mode = str(deep_cfg.get("mode") or "deep_mini")

    if not runner.exists():
        return DeepMiniRunArtifacts(
            status="runner_missing",
            success=False,
            prompt_path=str(prompt_path),
            summary_path=str(summary_path),
            executor_output_path=None,
            structured_packet_path=None,
            structured_packet=None,
            error=f"deep_research_runner_missing:{runner}",
        )

    command = [
        str(runner),
        "--mode",
        mode,
        "--input-file",
        str(prompt_path),
        "--workspace",
        str(workspace_root()),
        "--poll-seconds",
        str(poll_seconds),
        "--timeout-seconds",
        str(timeout_seconds),
        "--summary-json",
        str(summary_path),
    ]
    agent_id = deep_cfg.get("agent_id")
    if agent_id:
        command.extend(["--agent-id", str(agent_id)])

    try:
        completed = subprocess.run(
            command,
            cwd=workspace_root(),
            capture_output=True,
            text=True,
            timeout=max(timeout_seconds + 30, 60),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return DeepMiniRunArtifacts(
            status="timed_out",
            success=False,
            prompt_path=str(prompt_path),
            summary_path=str(summary_path),
            error=f"deep_research_timeout:{exc}",
        )
    except Exception as exc:
        return DeepMiniRunArtifacts(
            status="runner_error",
            success=False,
            prompt_path=str(prompt_path),
            summary_path=str(summary_path),
            error=f"deep_research_runner_error:{exc}",
        )

    summary = _read_summary(summary_path)
    executor_output = str(summary.get("executor_output") or "").strip()
    structured_packet = None
    if executor_output:
        executor_output_path.write_text(executor_output)
        parsed_packet = parse_deep_mini_output(
            executor_output,
            shortlist,
            {
                **context,
                "execution_eligible": context.get("execution_eligible") or shortlist,
                "route_chosen": summary.get("route_chosen") or mode,
            },
        ).to_dict()
        parse_blockers = [
            caveat
            for caveat in (parsed_packet.get("caveats") or [])
            if caveat == "best_pick_symbol_not_parsed_from_deep_mini_output"
            or str(caveat).startswith("deep_mini_json_missing_required_fields:")
        ]
        if not parse_blockers:
            structured_packet = parsed_packet
            structured_packet_path.write_text(json.dumps(structured_packet, indent=2, sort_keys=True))

    success = bool(completed.returncode == 0 and summary.get("success") is True)
    status = "completed" if success else "failed"
    error = None
    if not success:
        error = summary.get("error") or completed.stderr.strip() or completed.stdout.strip() or f"deep_research_exit_code:{completed.returncode}"

    return DeepMiniRunArtifacts(
        status=status,
        success=success,
        prompt_path=str(prompt_path),
        summary_path=str(summary_path) if summary_path.exists() else None,
        executor_output_path=str(executor_output_path) if executor_output else None,
        structured_packet_path=str(structured_packet_path) if structured_packet else None,
        structured_packet=structured_packet,
        route_chosen=str(summary.get("route_chosen") or "") or None,
        error=error,
        runner_stdout=completed.stdout.strip() or None,
        runner_stderr=completed.stderr.strip() or None,
    )
