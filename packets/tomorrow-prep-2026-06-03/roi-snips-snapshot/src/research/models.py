from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RawEvent:
    event_id: str
    source_name: str
    source_tier: int
    source_url: str
    discovered_at: str
    published_at: str | None
    updated_at: str | None
    headline: str
    raw_text: str
    company_name: str | None
    ticker_candidates: list[str]
    catalyst_type: str
    official_flag: bool
    structured_flag: bool
    social_flag: bool
    credibility_score_initial: float
    freshness_hours: float | None
    extraction_confidence: float
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateCluster:
    cluster_id: str
    primary_ticker: str
    company_name: str | None
    events: list[dict[str, Any]]
    catalyst_type_primary: str
    catalyst_types_all: list[str]
    first_seen_at: str
    latest_update_at: str
    official_sources: list[str]
    structured_sources: list[str]
    social_sources: list[str]
    obscure_sources: list[str]
    claim_summary: str
    official_confirmed: bool
    source_quality_score: float
    freshness_score: float
    crowdedness_preliminary: float
    unresolved_questions: list[str]
    elimination_flags: list[str]
    official_confirmation_count: int = 0
    structured_confirmation_count: int = 0
    social_confirmation_count: int = 0
    obscure_confirmation_count: int = 0
    catalyst_strength_score: float = 0.0
    attention_acceleration_score: float = 0.0
    story_stage_score: float = 0.0
    asymmetry_score: float = 0.0
    research_priority_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MarketOverlay:
    ticker: str
    observed_at: str
    prior_close: float | None
    last_premarket_price: float | None
    gap_pct: float | None
    premarket_volume: int | None
    premarket_dollar_volume: float | None
    average_20d_dollar_volume: float | None
    estimated_spread_pct: float | None
    halt_status: str | None
    market_cap: float | None
    price_band: str | None
    tradeability_gate_pass: bool
    tradeability_notes: list[str]
    execution_readiness_score: float = 0.0
    execution_blockers: list[str] = field(default_factory=list)
    execution_warnings: list[str] = field(default_factory=list)
    anti_chase_state: str | None = None
    opportunity_lifecycle_state: str | None = None
    entry_viability_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiscoveryCandidate:
    ticker: str
    source_names: list[str]
    discovery_score: float
    event_count: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchScorecard:
    ticker: str
    catalyst_strength_score: float
    freshness_score: float
    official_confirmation_count: int
    structured_confirmation_count: int
    social_confirmation_count: int
    attention_acceleration_score: float
    crowding_score: float
    asymmetry_score: float
    research_priority_score: float
    story_stage: str
    notes: list[str] = field(default_factory=list)
    hyper_trade_score: float = 0.0
    lane_tags: list[str] = field(default_factory=list)
    speculative_risk_penalties: list[str] = field(default_factory=list)
    validation_status: str = "unvalidated"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionGateDecision:
    ticker: str
    passed: bool
    execution_readiness_score: float
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerifiedCandidatePacket:
    ticker: str
    company: str | None
    catalyst_summary: str
    catalyst_type: str
    catalyst_published_at: str | None
    why_it_may_move_now: str
    official_source_urls: list[str]
    structured_source_urls: list[str]
    social_overlay_urls: list[str]
    hidden_edge_findings: list[str]
    source_quality_score: float
    momentum_attention_score: float
    tradeability_liquidity_score: float
    likely_not_fully_priced_score: float
    story_stage: str
    key_risks: list[str]
    why_it_might_fail: list[str]
    liquidity_flags: list[str]
    browser_verification_notes: str
    confidence_level: str
    verification_completed_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FinalDecisionPacket:
    decision_state: str
    generated_at: str
    market_session_target: str
    top_5_ranked: list[dict[str, Any]]
    best_single_pick: str | None
    exact_reason_best_pick_wins: str
    no_trade_list: list[dict[str, Any]]
    hidden_edge_findings: list[str]
    caveats: list[str]
    missing_inputs: list[str]
    operator_notes: str
    final_confidence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyBestPickPacket:
    generated_at: str
    best_pick: str | None
    shortlist: list[dict[str, Any]]
    execution_eligible: list[dict[str, Any]]
    executive_summary: str | None = None
    best_pick_summary: str | None = None
    why_best_pick_wins: str | None = None
    ranked_backups: list[dict[str, Any]] = field(default_factory=list)
    key_invalidation_risks: list[str] = field(default_factory=list)
    source_mode: str | None = None
    route_chosen: str | None = None
    caveats: list[str] = field(default_factory=list)
    research_leader: str | None = None
    why_market_may_not_be_fully_priced: str | None = None
    suggested_buy_zone: str | None = None
    same_day_upside_target: str | None = None
    one_to_three_day_upside_target: str | None = None
    thesis_break_level: str | None = None
    monitoring_timeframes: list[str] = field(default_factory=list)
    profit_taking_triggers: list[str] = field(default_factory=list)
    danger_signals: list[str] = field(default_factory=list)
    trade_authorization: dict[str, Any] = field(default_factory=dict)
    executable_primary: str | None = None
    buy_now_allowed: bool = False
    deterministic_fallback_executable_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
