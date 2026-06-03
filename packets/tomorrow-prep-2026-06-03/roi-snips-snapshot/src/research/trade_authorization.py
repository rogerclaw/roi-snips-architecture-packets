from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .strategy_fit import MEGA_CAPS


BLOCKING_DEEP_MINI_CAVEAT_PREFIXES = (
    "deep_mini_best_pick_out_of_shortlist:",
    "deep_mini_json_missing_required_fields:",
)
BLOCKING_DEEP_MINI_CAVEATS = {
    "best_pick_symbol_not_parsed_from_deep_mini_output",
    "deep_mini_required_for_live_research_not_completed",
    "deterministic_fallback_executable_allowed_false",
}
GOVERNED_RESEARCH_SOURCE_MODES = {"governed_deep_mini"}


@dataclass
class TradeAuthorization:
    authorized: bool
    ticker: str | None
    status: str
    blockers: list[str] = field(default_factory=list)
    deep_mini_selected_ticker: str | None = None
    one_ticker_only: bool = True
    deterministic_fallback_executable_allowed: bool = False
    same_style_backup_pool_ok: bool | None = None
    mega_cap_exceptional: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _symbol(value: Any) -> str | None:
    if isinstance(value, dict):
        raw = value.get("symbol") or value.get("ticker")
    else:
        raw = value
    text = str(raw or "").strip().upper()
    return text or None


def _has_blocking_caveat(caveats: list[Any]) -> bool:
    for caveat in caveats:
        text = str(caveat)
        if text in BLOCKING_DEEP_MINI_CAVEATS:
            return True
        if any(text.startswith(prefix) for prefix in BLOCKING_DEEP_MINI_CAVEAT_PREFIXES):
            return True
    return False


def authorize_one_ticker_trade(
    packet: dict[str, Any] | None,
    *,
    deep_mini_required: bool,
    deep_mini_completed: bool,
    same_style_backup_pool_ok: bool | None,
    executable_primary: dict[str, Any] | None = None,
) -> TradeAuthorization:
    packet = packet or {}
    ticker = _symbol(packet.get("best_pick"))
    executable_symbol = _symbol(executable_primary)
    blockers: list[str] = []

    if not ticker:
        blockers.append("deep_mini_selected_no_single_best_ticker")
    if packet.get("source_mode") not in GOVERNED_RESEARCH_SOURCE_MODES:
        blockers.append("not_governed_deep_mini_selection")
    if deep_mini_required and not deep_mini_completed:
        blockers.append("deep_mini_required_for_live_research_not_completed")
    if _has_blocking_caveat(list(packet.get("caveats") or [])):
        blockers.append("deep_mini_packet_has_blocking_caveats")
    if packet.get("deterministic_fallback_executable_allowed") is True:
        blockers.append("deterministic_fallback_marked_executable")
    if executable_symbol and ticker and executable_symbol != ticker:
        blockers.append("executable_primary_differs_from_deep_mini_pick")
    if same_style_backup_pool_ok is not True:
        blockers.append("same_style_backup_pool_not_green")

    mega_cap_exceptional: bool | None = None
    if ticker in MEGA_CAPS:
        mega_cap_exceptional = packet.get("exceptional_mega_cap_test_passed") is True
        if not mega_cap_exceptional:
            blockers.append("mega_cap_requires_explicit_exceptional_test")

    authorized = not blockers
    return TradeAuthorization(
        authorized=authorized,
        ticker=ticker if authorized else None,
        status="AUTHORIZED_ONE_TICKER" if authorized else "NO_TRADE_NOT_AUTHORIZED",
        blockers=sorted(set(blockers)),
        deep_mini_selected_ticker=ticker,
        deterministic_fallback_executable_allowed=False,
        same_style_backup_pool_ok=same_style_backup_pool_ok,
        mega_cap_exceptional=mega_cap_exceptional,
    )
