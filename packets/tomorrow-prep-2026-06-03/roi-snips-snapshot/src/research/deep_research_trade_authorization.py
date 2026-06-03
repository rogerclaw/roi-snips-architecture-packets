from __future__ import annotations

import json
from typing import Any

from .trade_authorization_ticket import ticket_from_final_packet, validate_ticket


def create_trade_authorization_ticket_from_deep_research(
    final_packet: dict[str, Any] | str,
    *,
    trading_date: str,
    completed_before_deadline: bool,
    research_model: str = "o4-mini-deep-research",
) -> dict[str, Any]:
    packet = json.loads(final_packet) if isinstance(final_packet, str) else dict(final_packet)
    ticket = ticket_from_final_packet(
        packet,
        trading_date=trading_date,
        completed_before_deadline=completed_before_deadline,
        research_model=research_model,
    )
    validation = validate_ticket(ticket)
    ticket["valid"] = validation.valid
    ticket["blockers"] = validation.blockers
    return ticket
