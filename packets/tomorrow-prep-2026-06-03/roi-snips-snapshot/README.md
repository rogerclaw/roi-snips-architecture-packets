# Roi Snips

Self-hosted U.S. equities trading/research system for the Alpaca-unified v5 runtime.

## Current live architecture
- Broker/execution: **Alpaca Trading API**
- Market data: **Alpaca Market Data API**
- News: **Alpaca news + SEC EDGAR + optional Benzinga/Reddit/X overlays**
- Strategy family: `CatalystContinuationLong`
- Direction: long-only U.S. stocks + ETFs
- Max open positions: `1`
- Live order submission is disabled by default unless `ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=true`
- Paper order submission is disabled by default unless `ROI_SNIPS_ALLOW_PAPER_ORDER_SUBMISSION=true`
- New entries are restricted to `09:30-11:00 ET`; valid live triggers are `OPENING_DRIVE_LONG`, `ORB_BREAK`, and `VWAP_RECLAIM`.

## Current runtime shape
- Alpaca adapters: `src/adapters/alpaca_*.py`
- Research ingestion + clustering + gates: `src/research/`
- Premarket report builder: `src/workflows/premarket_pipeline.py`
- Autonomous live monitor: `src/workflows/live_monitor.py`
- Command/status/flat-all handling: `src/approval/`
- Deterministic routing + audit logging: `src/execution/`
- Scheduler: `src/workflows/scheduler.py`

## Canonical config
- `configs/live.yaml`
- `config/agent.yaml`
- `config/risk.yaml`
- `config/workflow.yaml`
- `.env.example`

## Quick start
1. Copy `.env.example` to `.env` and fill Alpaca + data + Telegram + Postgres secrets.
2. Bootstrap the runtime environment: `scripts/bootstrap_env.sh`
3. Start dependencies: `docker compose up -d`
4. Apply DB migrations in `migrations/`
5. Run mechanical checks: `scripts/run_mechanical_checks.sh`
   - default bounded smoke path skips governed deep-mini
   - set `ROI_SNIPS_MECHANICAL_CHECKS_RUN_DEEP_MINI=true` to include governed deep-mini
6. Generate a premarket report: `scripts/run_premarket.sh`
7. Run the live monitor once: `scripts/run_live_monitor.sh`
8. Optional continuous monitor: `scripts/run_live_monitor.sh --loop`
9. Optional Telegram/operator loop: `scripts/run_operator_bot.sh`
10. Optional scheduler: `scripts/run_scheduler.sh`

## Safe paper-first validation
- Paper config: `configs/paper.yaml`
- Paper readiness: `scripts/check_paper_readiness.sh`
- Paper monitor: `scripts/run_paper_monitor.sh [--loop]`
- Paper submission fails closed unless config, env, broker runtime, and deterministic guards all agree on paper mode.

## Launch posture
- Start with read-only validation mornings first.
- Verify account, quotes, bars, proposals, logging, and flatten behavior before arming live submission.
- Keep `ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=false` until the live Alpaca health path is fully verified.
- Prefer paper validation first; paper arming will fail closed if the runtime still points at live.

## Opening-drive v2 posture
- Premarket research should narrow to one best name plus backups before 09:29 ET.
- `OPENING_DRIVE_LONG` can trigger from a sampled sub-minute bell path once quote/tape persistence, projected first-minute volume, spread, chase, and invalidation guards pass.
- If sub-minute confirmation is not ready, `OPENING_DRIVE_LONG` can still trigger from the first completed 1-minute structure once the first-minute bar confirms real demand.
- `ORB_BREAK` and `VWAP_RECLAIM` remain valid continuation entries after 09:35 ET when opening-drive conditions fail or the move needs more confirmation.

## Legacy archive
Old Webull-era adapters/tests were removed from the active runtime path and archived under `archive/webull/`.
