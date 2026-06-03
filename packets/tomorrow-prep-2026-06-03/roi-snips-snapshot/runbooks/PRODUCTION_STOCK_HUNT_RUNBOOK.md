# Roi Snips Production Stock Hunt Runbook

Purpose: run Roi Snips as an aggressive but gated same-day to 1-3 day long-only U.S. stock/ETF research and execution system. This runbook covers the current hyper-speculative posture, optional Grok/X discovery, explicit live arming, and mechanical-only live blockers.

## Mission

Find one decisive high-upside stock/ETF candidate, not a conservative watchlist. The system should prefer fresh hard catalysts, unusual attention/tape, and asymmetric volatility while preserving deterministic no-trade and execution gates.

Hard constraints:

- U.S. stocks/ETFs only.
- Long-only.
- No options.
- No shorting.
- No margin behavior.
- One open position max.
- Entries only during configured entry windows.
- Live trading stays disabled unless Charles explicitly arms it.
- The LLM never has direct order authority; deterministic code places, cancels, or replaces orders after mechanical gates pass.

## Required Production Inputs

- Alpaca live broker credentials.
- Alpaca SIP market data entitlement.
- OpenAI API key for governed deep-research / deep-mini runner if final LLM synthesis is enabled.
- Optional social/X source lane, such as Grok, treated only as discovery evidence.
- Current Roi Snips config files:
  - `configs/live.yaml`
  - `config/workflow.yaml`
  - `config/risk.yaml`
- Explicit runtime guard state:
  - `state/LIVE_ARMED`
  - `state/DISABLE_NEW_ENTRIES`
  - kill-switch state
  - force-flat state
- Operator contact path for alerts and final packet delivery.

## Pre-Run Checks

Run these before trusting a morning pick:

1. Market calendar and session phase.
2. Alpaca account health.
3. Open orders = zero unless deliberately managing an existing position.
4. Existing positions = zero before new-entry mode.
5. SIP quote, trade, bars, bid/ask, spread, previous close, and VWAP fields available.
6. PDT / buying-power / cash status.
7. `state/LIVE_ARMED`, `state/DISABLE_NEW_ENTRIES`, and kill-switch status understood.
8. Research scouts producing fresh events.
9. Deep-research runner key present if governed synthesis is required.
10. Tests pass after any code/config change.

Safe readiness command:

```bash
scripts/check_live_readiness.sh
```

## Discovery Lanes

Use multiple lanes; never rely on one LLM or one social source:

- SEC filings.
- Company IR / press releases.
- Newswire and earnings/guidance updates.
- FDA / biotech catalysts.
- Government contracts, policy, grants, procurement, legal/regulatory actions.
- Exchange / halt / unusual mover signals.
- Market tape: gap, relative volume, premarket dollar volume, spread, VWAP, ORB/opening range.
- Social/X chatter and attention acceleration.
- Obscure source discovery for under-covered names.

## Online AI Deep-Research Procedure

This is the production equivalent of Charles's manual ChatGPT Pro stock-search workflow. It must use the governed OpenAI deep-research runner, not an ad-hoc chat reply.

Inputs:

- Dynamically discovered candidate list from research scouts.
- Evidence ledger for each candidate: official source, structured news, social/attention hints, market/tape overlay, and rejection flags.
- Current market context: session phase, premarket/early tape, spread, liquidity, RVOL, VWAP/opening range when available.
- Charles's target style: one aggressive high-upside same-day to 1-3 day pick, not a generic watchlist.

Routing:

1. Use deterministic scouts first to build and rank a broad universe.
2. Send the top execution-eligible or near-eligible candidates to `tools/deep-research-runner`.
3. Let the research architect classify the request as `no_escalation`, `deep_mini`, or `deep`.
4. Use `o4-mini-deep-research` for most morning shortlist synthesis.
5. Use `o3-deep-research` only when the decision is unusually ambiguous, high-stakes, broad, or source-conflicted.
6. If the runner fails, produce a deterministic fallback packet clearly marked as not deep-researched.

Expected command shape:

```bash
tools/deep-research-runner \
  --mode deep_mini \
  --input-file <generated_shortlist_brief.txt> \
  --workspace /Users/rogerclaw/.openclaw/workspace/roi-snips \
  --summary-json <run_output_summary.json>
```

The runner attaches web-search tooling through the OpenAI Responses API when escalation is approved. It logs the route, model, generated brief, tool usage metadata, output memo, and structured packet.

The generated brief must ask for:

- one single best stock/ETF, plus ranked backups only for comparison
- exact catalyst and source evidence
- why the move may not be fully priced
- sentiment/discussion trend
- current tape/tradeability context
- buy zone / entry framework
- same-day and 1-3 day targets
- thesis-break level
- profit-taking triggers
- danger signals
- execution/liquidity risks
- why the winner beats the backups

Deep research is not allowed to override:

- mechanical market-data requirements
- mechanical liquidity/spread impossibility gates
- stale-data checks
- one-position rule
- kill switch / disable-new-entries / live-armed state
- long-only U.S. stocks/ETFs scope
- no options / no shorts / no margin

Existing source prompts and calibration docs:

- `docs/CHARLES_GPT_PRO_RESEARCH_EMAIL_2026-05-01.md`
- `ops/research/2026-04-30_deep_mini_architecture_rebuild_prompt.txt`
- `src/workflows/deep_mini_bridge.py`

## Research Channel Setup Backlog

Already usable / configured:

- Alpaca SIP quote/trade/bar market data.
- Alpaca account/order/position checks.
- Alpaca News.
- Benzinga newswire.
- SEC EDGAR.
- Company IR / press-release page discovery.
- FDA / biotech keyword scout.
- Government/contract keyword scout.
- Exchange / mover scout.
- Reddit public JSON fallback for weak retail-attention discovery; authenticated Reddit API credentials are still preferred but not required for research mode.
- Grok/X search through OpenClaw as an optional social discovery lane.
- Governed OpenAI deep-research runner.

Highest-value missing or weak channels:

- Reddit API credentials and validated expanded subreddit set for more reliable retail attention acceleration.
- Grok query tuning and richer audit persistence for full response JSON / query templates.
- Stocktwits/social ticker-stream source for fast retail ticker chatter.
- Float / shares outstanding / short interest source for squeeze and low-float context.
- Dedicated premarket mover/gapper source independent of Alpaca/Benzinga, to cross-check top movers.
- ClinicalTrials.gov / FDA calendar-style biotech event source for trial, PDUFA, clearance, and advisory dates.
- Government contract/procurement source beyond keyword news, especially SAM.gov, USAspending, and agency award notices.
- Earnings/calendar and analyst-action source, including earnings surprise, guidance, and rating/price-target moves.
- Web search/news discovery fallback such as Brave/SerpAPI/Crawl4AI for obscure catalysts not surfaced by feeds.

Lower priority:

- Options flow. Roi Snips does not trade options, but unusual option activity can be a supporting attention signal.
- Insider/institutional transaction source. Useful for context, rarely decisive for same-day trades.
- Borrow/short-availability feed. Useful for squeeze context, not required for long-only execution.

## Evidence Ledger Rules

Every candidate should record:

- ticker and company mapping
- catalyst claim
- official source URLs where available
- structured/news source URLs
- social/source citations
- freshness
- story stage: early, developing, late, crowded, exhausted
- attention acceleration
- crowding/pump risk
- hidden-edge / why-not-priced rationale
- unresolved questions
- rejection flags

Social-only claims may discover candidates but cannot prove a business thesis. Social + premarket repricing + opening tape can become a momentum trade only through `SOCIAL_TAPE_ROCKET`, with reduced/default-capped sizing and all mechanical gates still enforced.

## Ranking Rules

Primary scoring overlay is now `hyper_trade_score`, designed to optimize for explosive short-term repricing rather than company quality. It blends premarket repricing energy, catalyst violence, opening-drive potential, attention velocity, earlyness, float/squeeze factors, level clarity, and source quality, then subtracts exhaustion, dilution/offering, fake-hype, and mega-cap boring penalties.

Prefer:

- fresh hard catalysts
- official or structured confirmation
- high asymmetry
- still-early story stage
- unusual but tradeable attention/volume
- smaller or lesser-known names when quality is comparable

Penalize:

- mega-cap default picks without exceptional catalyst/tape
- hype-only setups
- stale catalysts
- parabolic/exhausted moves
- missing source confirmation
- wide spreads
- poor liquidity
- unclear ticker mapping

## Execution Gates

Research enthusiasm cannot override these:

- valid tradable U.S. ticker
- live-armed state present when live entry mode is requested
- disable-new-entries absent
- kill-switch absent
- quote and last price present
- bid/ask and spread present
- no halt / abnormal no-quote state
- session phase allows entries
- one-position rule passes
- broker/account state healthy

Speculative traits are not default hard blockers. Low float, sub-$5 price, social hype, high gap percent, poor company quality, and wide-but-tradeable spreads should affect `hyper_trade_score`, size, entry mode, and exit urgency. They block only when they become mechanically impossible or unsafe to execute.

If no candidate passes mechanical gates, the correct output is a research leader or no-trade packet, not an executable best pick.

## Final Output Packet

The final report to Charles must include:

- best ticker/company or explicit no-trade
- catalyst
- why the move may not be fully priced
- evidence and sentiment/attention trend
- buy zone / entry framework
- same-day target
- 1-3 day target
- downside / thesis-break level
- monitoring timeframe
- profit-taking triggers
- danger signals
- why it beats backups
- execution gate status
- live-trading guard status

## Arming Live Trading

Before live entries can be armed:

1. Charles explicitly says to arm live trading.
2. `scripts/check_live_readiness.sh` is green except for the guard state that will be intentionally changed.
3. Current run has one executable candidate or an intentional no-trade.
4. Max position size / risk budget is confirmed in config.
5. `state/LIVE_ARMED` is created deliberately.
6. `state/DISABLE_NEW_ENTRIES` is cleared deliberately.
7. First live run is monitored actively.

Do not infer arming from API keys, account funding, market-data upgrade, or research success.

## Failure Handling

- Bad/stale quotes: disable new entries.
- Market data degradation: no live entries; research mode only.
- Broker/account mismatch: disable new entries and reconcile.
- Existing unexpected position/order: stop, reconcile, and flatten only under the configured incident path.
- Missing protection or exit logic: no entry.
- LLM/deep-research failure: use deterministic fallback packet, clearly marked.
- Source conflict: prefer official/company/SEC evidence over social claims.

## Validation

Minimum validation after changes:

```bash
PYTHONPATH=. .venv/bin/pytest tests
scripts/check_live_readiness.sh
scripts/check_opening_bell_readiness.sh
```

## Opening-Bell Hyper Execution Layer

The opening-bell patch adds a dedicated `OPENING_BURST_HYPER_LONG` layer rather than treating the first minute as a loose ORB/VWAP exception.

New deterministic modules:

- `src/features/opening_tape.py` converts quote/trade events into first-5s/10s/15s/30s/60s OHLCV, dollar volume, micro-VWAP, spread regime, bid refresh, ask lift, bid collapse, wick/rug/chase risk, `opening_drive_score`, and `open_execution_confidence`.
- `src/strategy/opening_burst_hyper_long.py` decides whether the first 10s/30s/60s tape confirms a buy signal before 09:31, using aggressive but bounded thresholds.
- `src/execution/opening_burst_executor.py` converts confirmed signals into capped aggressive limit-order plans. It still routes through the existing deterministic order router, so `LIVE_ARMED`, `DISABLE_NEW_ENTRIES`, `KILL_SWITCH`, entry-window, position, preview, and broker runtime checks remain binding.
- `src/execution/fast_cancel.py` cancels weak, stale, unfilled, over-cap, or flipped-tape opening orders quickly.
- `src/execution/opening_position_manager.py` manages the first minutes after fill, exiting on thesis break, bid collapse, opening-drive failure, stale/no-quote state, or time-stop failure.
- `src/workflows/opening_bell_monitor.py` provides the opening-bell readiness entrypoint.

Runtime command:

```bash
PYTHONPATH=. .venv/bin/python -m src.workflows.opening_bell_monitor --readiness-only
```

Hardened live runner for the 2026-05-21 armed opening-bell run:

```bash
ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=true scripts/run_opening_bell_live_monitor.sh
```

The runner performs live readiness and opening-bell readiness before entering the
monitor loop, writes the loop output to `reports/live_monitor/`, and stops at
the configured entry-window end. It is the production command the 06:29:30 PT
OpenClaw cron should call. The runner still uses `src.workflows.live_monitor` as
the production execution loop; the newer opening-bell modules are tested
building blocks and scaffolding for the next streaming-supervisor phase.

Readiness command:

```bash
scripts/check_opening_bell_readiness.sh
```

Expected fail-closed state before Charles explicitly arms live entry is `YELLOW: research only / no live order` with blockers limited to `live_armed_missing` and `disable_entries_active`. Any market-data, broker, cash, quote, halt, duplicate-order, or monitor-path blocker is `RED`.

Current known production posture as of 2026-05-20:

- Alpaca live broker access works.
- Alpaca SIP market data works after Algo Trader Plus upgrade.
- OpenAI general model access works through OpenClaw, and the shared `tools/deep-research-runner` can now load the local OpenClaw OpenAI key when the shell does not export `OPENAI_API_KEY`.
- Governed deep-research runner smoke test passes on a no-escalation routing request.
- Grok/X search is usable through OpenClaw and has a first structured Roi Snips social-scout integration.
- Reddit authenticated API credentials are not configured yet; the Reddit adapter currently uses public JSON fallback and must remain non-blocking.
- Hyper-speculative scoring/lane scaffolding is implemented: `hyper_trade_score`, `VERIFIED_CATALYST_RUNNER`, `SOCIAL_TAPE_ROCKET`, and `MOVER_FIRST_EXPLAIN_LATER`.
- Opening-bell scaffolding is implemented: `OPENING_BURST_HYPER_LONG`, first-seconds tape features, capped aggressive limit signal generation, fast cancel decisions, post-fill opening position management, `config/opening_bell.yaml`, and `scripts/check_opening_bell_readiness.sh`.
- Charles explicitly armed the 2026-05-21 live opening-bell run at 2026-05-20 21:16 PT.
- Current armed posture: `state/LIVE_ARMED` exists, `state/DISABLE_NEW_ENTRIES` is absent, and `state/KILL_SWITCH` is absent.
- With `ROI_SNIPS_ALLOW_LIVE_ORDER_SUBMISSION=true`, live readiness and opening-bell readiness report green/no blockers as of the arming checks.
- OpenClaw cron `f112f794-a79f-418c-9aaa-d0af8c737097` is the bounded 2026-05-21 06:29:30 PT opening-bell live monitor job and calls `scripts/run_opening_bell_live_monitor.sh`.
- Grok is optional and wired only as a discovery lane.

Current remaining blockers before live entries:

- No static blocker is currently expected while the above armed posture holds.
- A live order may still be blocked by morning research producing no executable primary, failed opening tape, stale/missing quote, missing bid/ask, halt/no quote, broker/account/cash/tradability failure, duplicate/existing order or position, entry cap/chase checks, or any guard reappearing.
- The current production loop is polling-based, not the full future Alpaca quote/trade streaming supervisor.
