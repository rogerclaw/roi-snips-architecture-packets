# Roi Snips Operator Daily Checklist

## Discovery health
- Confirm the overnight/dynamic discovery pipeline is producing discovered symbols.
- Confirm structured news / SEC / social discovery sources are not all dark at once.
- Read the latest research manifest and morning report.
- If discovery is empty, verify whether the market is genuinely quiet before treating it as a system issue.

## Research health
- Confirm the ranked research shortlist exists.
- Confirm lesser-known catalyst names can appear; no static mega-cap fallback should be assumed.
- Validate the no-trade / blocked list.
- Confirm governed deep-mini shortlist artifact exists when a meaningful shortlist is present.

## Execution health
- Run `scripts/check_paper_readiness.sh` first for bounded paper validation.
- Run `scripts/check_live_readiness.sh` before attempting live trading.
- Confirm the configured broker provider account access is healthy.
- Confirm the configured market-data provider quote/bar path is healthy enough for deterministic execution.
- Confirm Telegram/operator controls are responsive.
- Confirm kill-switch and flat-all paths are available.
- Remember: research may still be usable when quote path is degraded, but live execution must fail closed unless data guards are green.
- Current known failure modes worth checking explicitly:
  - Alpaca full live execution blocks if SIP-entitled recent quotes are unavailable (`alpaca_quote_unavailable:{"message":"subscription does not permit querying recent SIP data"}`)
  - Webull runtime cannot be selected as the active live path until real `WEBULL_APP_KEY` / `WEBULL_APP_SECRET` credentials are populated and trading endpoints are configured if signed REST coverage is insufficient

## During session
- Monitor proposals, open orders, fills, and exits.
- If stale quotes, broken broker state, or stream/account mismatch appears, disable new entries immediately.
- Operator commands: `STATUS`, `DISABLE NEW ENTRIES`, `ENABLE NEW ENTRIES`, `FLAT ALL NOW`, `EXECUTE ENTRY <plan_id>` (optional manual override), `REJECT ENTRY <plan_id> [reason]`.
- Autonomous live order placement is allowed when live submission is armed and deterministic guards are green; `EXECUTE ENTRY <plan_id>` remains optional override/audit handle, not a prerequisite approval step.

## Useful readiness commands
- Safe paper readiness: `scripts/check_paper_readiness.sh`
- Paper monitor: `scripts/run_paper_monitor.sh`
- Default configured providers: `scripts/check_live_readiness.sh`
- Probe Alpaca explicitly: `ROI_SNIPS_READINESS_BROKER_PROVIDER=alpaca ROI_SNIPS_READINESS_MARKET_DATA_PROVIDER=alpaca scripts/check_live_readiness.sh`
- Probe Webull explicitly: `ROI_SNIPS_READINESS_BROKER_PROVIDER=webull ROI_SNIPS_READINESS_MARKET_DATA_PROVIDER=webull scripts/check_live_readiness.sh`
- One-shot live monitor: `scripts/run_live_monitor.sh`

## Post-session
- Confirm positions are zero.
- Confirm working orders are zero.
- Confirm audit logs exist for proposal/order/cancel/flatten paths.
- Review any rejected, cancelled, or force-flattened trades.
