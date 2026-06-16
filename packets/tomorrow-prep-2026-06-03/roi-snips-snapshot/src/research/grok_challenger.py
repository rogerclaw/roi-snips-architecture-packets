from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def run_grok_challenger(openai_ticket: dict[str, Any] | None, grok_candidates: list[dict[str, Any]] | None) -> dict[str, Any]:
    ticket_ticker = str((openai_ticket or {}).get("authorized_ticker") or "").upper()
    candidates = list(grok_candidates or [])
    challenger_symbols = [str(row.get("ticker") or row.get("symbol") or "").upper() for row in candidates if row.get("ticker") or row.get("symbol")]
    disagreement = bool(ticket_ticker and challenger_symbols and ticket_ticker not in challenger_symbols[:3])
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "role": "challenger_research_only",
        "openai_authorized_ticker": ticket_ticker or None,
        "grok_candidate_symbols": challenger_symbols,
        "disagreement": disagreement,
        "recommended_action": "RERUN_OR_NO_TRADE_UNTIL_NEW_OPENAI_TICKET" if disagreement else "KEEP_OPENAI_TICKET_IF_OTHER_GATES_PASS",
        "can_authorize_live_trade": False,
        "executable_primary": None,
    }
