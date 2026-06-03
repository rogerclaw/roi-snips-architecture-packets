from __future__ import annotations

import argparse
import json
from typing import Any

from ..common.config import load_live_config
from ..common.provider_factory import build_live_readiness_report


def _override_provider(cfg: dict[str, Any], *, broker_provider: str | None, market_data_provider: str | None) -> dict[str, Any]:
    out = json.loads(json.dumps(cfg))
    if broker_provider:
        out.setdefault("broker", {})["provider"] = broker_provider
    if market_data_provider:
        out.setdefault("market_data", {})["provider"] = market_data_provider
    return out


def run_live_readiness(
    *,
    probe_symbol: str = "SPY",
    broker_provider: str | None = None,
    market_data_provider: str | None = None,
    cfg: dict[str, Any] | None = None,
    inspect_broker_state: bool = True,
) -> dict[str, Any]:
    cfg = _override_provider(cfg or load_live_config(), broker_provider=broker_provider, market_data_provider=market_data_provider)
    return build_live_readiness_report(
        cfg,
        probe_symbol=probe_symbol,
        broker_provider=broker_provider,
        market_data_provider=market_data_provider,
        inspect_broker_state=inspect_broker_state,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit provider-aware Roi Snips live readiness diagnostics")
    parser.add_argument("--probe-symbol", default="SPY")
    parser.add_argument("--broker-provider", default=None)
    parser.add_argument("--market-data-provider", default=None)
    parser.add_argument(
        "--skip-broker-state",
        action="store_true",
        help="Do not inspect live broker account, orders, or positions; report as not execution-ready.",
    )
    args = parser.parse_args()
    result = run_live_readiness(
        probe_symbol=args.probe_symbol,
        broker_provider=args.broker_provider,
        market_data_provider=args.market_data_provider,
        inspect_broker_state=not args.skip_broker_state,
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
