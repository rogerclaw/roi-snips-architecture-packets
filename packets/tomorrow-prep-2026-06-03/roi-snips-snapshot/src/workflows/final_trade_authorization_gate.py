from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from ..common.config import repo_root
from ..research.trade_authorization_ticket import load_today_ticket, validate_ticket


def run_final_trade_authorization_gate(trading_date: str | None = None) -> dict[str, object]:
    ticket = load_today_ticket(repo_root(), trading_date)
    validation = validate_ticket(ticket)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "trading_date": trading_date,
        "verdict": "GO" if validation.valid else "NO_GO",
        "ticket_valid": validation.valid,
        "ticket_status": validation.status,
        "authorized_ticker": (ticket or {}).get("authorized_ticker"),
        "authorized_strategy": (ticket or {}).get("authorized_strategy") or (ticket or {}).get("strategy"),
        "blockers": validation.blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Roi Snips single-ticker trade authorization ticket.")
    parser.add_argument("--trading-date")
    args = parser.parse_args()
    result = run_final_trade_authorization_gate(args.trading_date)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verdict"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
