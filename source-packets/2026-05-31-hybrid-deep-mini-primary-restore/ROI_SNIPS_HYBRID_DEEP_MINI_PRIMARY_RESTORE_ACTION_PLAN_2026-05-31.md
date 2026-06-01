# Roi Snips Hybrid Research Restore Action Plan

Generated: 2026-05-31 17:40 PT

## Directive Implemented

Restore the intended hybrid architecture:

- Grok/X finds social heat, early chatter, and suspicious velocity.
- Grok web verification may quickly challenge or annotate social claims.
- Governed OpenAI deep-mini/deep research is the primary live stock picker.
- Only governed OpenAI deep-mini/deep output may create a live-valid Trade Authorization Ticket.
- Deterministic code may trade only the ticket-authorized ticker, and only after market-data, risk, broker, and live-arming guards pass.

## Code Changes

- `scripts/run_live_trade_ready_premarket.sh`
  - Restored `ROI_SNIPS_SKIP_DEEP_MINI=false`.
  - Restored `ROI_SNIPS_REQUIRE_DEEP_MINI_FOR_LIVE_RESEARCH=true`.
  - Changed Grok to run as a heat/input layer before the governed deep research pipeline.
  - Added an explicit governed deep research pipeline step whose status is recorded separately.

- `scripts/run_research_pipeline.sh`
  - Default route is now `src.workflows.research_pipeline`.
  - `src.workflows.grok_research_pipeline` is available only when `ROI_SNIPS_GROK_HEAT_ONLY=true`.

- `src/workflows/grok_research_pipeline.py`
  - Grok no longer writes `runs/<date>/trade_authorization_ticket.json`.
  - Grok writes `runs/<date>/grok/ticket_input_summary.json` for deep-mini/deep to judge.
  - Manifest now states Grok is research-only and cannot authorize live trading.

- `src/workflows/research_pipeline.py`
  - A stale `ROI_SNIPS_REQUIRE_GROK_FOR_LIVE_RESEARCH=true` no longer converts the primary research mode to Grok.
  - Live primary deep research modes are restricted to `deep_mini` or `deep`.

- `src/workflows/scheduler.py`
  - Scheduled research jobs now invoke `ResearchPipeline().run_once()` instead of the Grok pipeline.

- Tests were updated to enforce the restored boundary.

## How Tomorrow Works

All times are Pacific unless otherwise installed in cron.

1. `04:45` brokerless Grok canary runs.
   - Purpose: confirm Grok/X and Grok web paths are usable.
   - It must not inspect broker/account/order/position state.
   - It must not create a live Trade Authorization Ticket.

2. `05:00` discovery runs.
   - Deterministic sources, market/news inputs, and social discovery build raw candidate context.
   - Grok/X contributes heat, velocity, and thread context.

3. `05:10`, `05:45`, `06:10` premarket research passes run.
   - Grok heat artifacts are written under `runs/2026-06-01/grok/`.
   - Governed OpenAI deep-mini/deep research runs as the primary selector through `src.workflows.research_pipeline`.
   - If deep-mini/deep does not complete, the system must stay `NO_TRADE_RESEARCH_INCOMPLETE`.
   - If deep-mini/deep selects one ticker and produces valid required artifacts before deadline, the pipeline may write the only live-valid `runs/2026-06-01/trade_authorization_ticket.json`.

4. `06:20` and `06:25` final live arming gates run.
   - They validate the same-day ticket, freshness, live market readiness, and deterministic risk/broker guard state.
   - Broker/account/order/position cleanliness checks belong here, inside the authorized deterministic guarded live run.
   - If any guard fails, `DISABLE_NEW_ENTRIES` remains present and `LIVE_ARMED` remains absent.

5. `06:28` opening monitor starts.
   - It may consider only the ticket-authorized ticker.
   - Backups, Grok picks, deterministic rankings, and social-only names are research-only.
   - No live order path can proceed unless final readiness is GREEN and the ticket authorizes the exact symbol and strategy family.

6. `12:45` force-flat safety runs.
   - It remains the defensive cleanup guard for live-day exposure.

## Acceptance Evidence

Focused verification passed:

```text
bash -n scripts/run_live_trade_ready_premarket.sh scripts/run_research_pipeline.sh scripts/run_final_live_arming_gate.sh scripts/run_opening_bell_live_monitor.sh
.venv/bin/python -m pytest tests/test_deep_mini_not_skipped_in_live_wrapper.py tests/test_deep_research_routing.py tests/test_grok_no_direct_order_authority.py tests/test_research_pipeline.py tests/test_trade_authorization_ticket.py
25 passed in 0.13s
```

## Explicit Non-Actions

- No broker account state was inspected.
- No broker order state was inspected.
- No broker position state was inspected.
- No order preview/place/submit/replace/cancel path was used.
- No live guard file was armed from this jog.

## Remaining Live Conditions

Monday live autonomy is still conditional on:

- same-day successful discovery and Grok heat input,
- governed OpenAI deep-mini/deep primary research completing before deadline,
- one valid same-day Trade Authorization Ticket from OpenAI deep-mini/deep,
- fresh candidate-specific market data and tape confirmation,
- GREEN final live arming gate,
- deterministic broker/account/order/position cleanliness checks inside the authorized guarded run,
- `LIVE_ARMED` written and `DISABLE_NEW_ENTRIES` cleared by the final arming gate only.
