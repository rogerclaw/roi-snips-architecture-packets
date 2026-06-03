# Roi Snips Master Stock-Pick SOP

Last updated: 2026-05-01

## Purpose
Run Roi Snips as a high-conviction, catalyst-first, long-only U.S. equity stock picker and execution engine optimized for Charles's preferred style: one best high-risk short-term idea, strong opening-bell awareness, and rapid post-entry monitoring.

## Non-negotiable hard guards
- Long-only U.S. stocks/ETFs only
- No shorting
- No options
- No margin behavior
- One open position max
- Intraday-only execution posture in v2
- Valid live entry window: 09:30 ET to 11:00 ET
- `OPENING_DRIVE_LONG` only during 09:30:00-09:34:59 ET, using either sampled sub-minute confirmation or first-minute bar confirmation
- `ORB_BREAK` and `VWAP_RECLAIM` remain valid after 09:35 ET
- Force flat by 15:45 ET

## Primary user objective
Find exactly one best high-risk short-term stock idea for same-day to 1-3 day upside, not a generic watchlist.

## Preferred answer style
- Similar to ChatGPT Pro / GPT-5.5 deep research outputs
- Decisive single-name recommendation
- Heavy emphasis on fresh verified catalyst, stacked catalyst strength, sentiment, volume, technical structure, and invalidation
- Must explain why the winner beats other visible gappers
- Must include execution-aware buy range, no-chase framing, targets, and danger signals

## Research architecture

### Phase 1 - Overnight and premarket discovery
Run broad discovery before the open across:
- SEC / EDGAR
- company IR / press releases
- earnings releases and guidance
- structured news wires
- market-data gap / volume scans
- Reddit / StockTwits / X / forum acceleration
- sector newsletters / blogs / high-signal commentary

Goal:
- Build a dynamic universe of catalyst names early
- Prioritize names with real repricing potential, not only quality bias
- Have A/B/C tiers and one provisional best pick ready before the bell

### Phase 2 - Full deep research first, bounded synthesis second
Use full deep research for broad premarket ranking when multiple serious candidates exist.

Then use bounded synthesis for the narrowed shortlist to answer:
- which single candidate is best
- why it beats the others
- how it should be executed
- what invalidates it fastest

Operating guidance:
- Full deep research is preferred for broad discovery.
- Bounded synthesis is preferred after the shortlist is already narrowed.
- Never rely on bounded synthesis alone as the whole discovery engine for Charles's style.

### Phase 3 - Bell readiness and opening-drive evaluation
Before and just after the bell, evaluate:
- premarket high / low
- spread quality
- first-minute volume and dollar volume
- first-minute close quality
- whether the open is accepted or rejected
- whether the move is a true opening drive or a gap-and-fade trap

If a prequalified catalyst name passes the bell checks, `OPENING_DRIVE_LONG` is allowed.

### Phase 4 - Deterministic execution window
Valid triggers:
- `OPENING_DRIVE_LONG`
- `ORB_BREAK`
- `VWAP_RECLAIM`

Trigger policy:
- `OPENING_DRIVE_LONG`: use only for prequalified catalyst names with strong sub-minute or first-minute confirmation, tight spreads, manageable chase distance, and clear invalidation.
- `ORB_BREAK`: use after 09:35 ET when a strong name breaks the opening range with volume confirmation.
- `VWAP_RECLAIM`: use after a pullback hold and reclaim when the tape improves.

No trade if:
- spreads are too wide
- catalyst evidence degrades
- price action fails at the open, opening range, or VWAP
- dilution / offering / halt / stale-data risk appears
- the move is already too extended for defined risk

## Ranking rubric
Weight candidates by:
1. Primary-source catalyst strength
2. Catalyst stack strength
3. Repricing potential relative to market cap / float
4. Relative volume and attention acceleration
5. Opening-drive readiness
6. Technical tradeability and invalidation clarity
7. Execution quality / spread / liquidity

## Opening-drive ruleset
Minimum opening-drive requirements:
- prequalified catalyst name from premarket research
- real premarket participation
- acceptable spread at the open
- strong first-minute volume and dollar volume
- strong first-minute close quality
- still inside chase limits versus the key reference level
- clear stop / thesis-break level

Hard no-trade examples:
- broken spread
- one-candle blowoff with no structure
- immediate loss of opening print or first-minute low
- weak evidence / rumor-only setup
- stale or unhealthy live data

## Monitoring model after entry
### Sub-minute / every few seconds if possible
Watch:
- last price
- bid/ask
- spread
- whether buyers keep lifting offers
- whether price is holding above open / VWAP / first pivot
- whether the move still looks orderly

### Every 1 minute
Watch:
- candle close quality
- volume versus prior minute
- higher-high / higher-low structure
- failed breakout attempts
- wick size and rejection behavior
- momentum acceleration or decay

### Every 5 minutes
Watch:
- whether the trade is following through or stalling
- whether the broader intraday structure still supports the thesis

## Common failure modes to avoid
- Overweighting "good company" or blue-chip quality over short-term explosiveness
- Picking names that are moving without a hard reason
- Ignoring spread risk and execution practicality
- Confusing chatter with catalyst
- Missing catalyst-size-versus-market-cap asymmetry
- Missing opening-drive names because the engine waits too long
- Misreading screenshots or performance comparisons

## Prompt/version management
- Save durable prompt versions under `roi-snips/prompts/`
- Keep the user's preferred prompt wording archived, not paraphrased away
- Update discovery, shortlist, final memo, and monitoring prompts when the preferred prompt shape improves
- Keep this SOP as the master runbook and refine it as the live system improves

## Research tools and external engines to compare
Primary search / evidence sources:
- SEC / EDGAR
- company IR
- structured news wires
- market data / volume overlays

Helpful external LLM or search complements:
- ChatGPT Pro deep research
- Claude for alternate synthesis / critique
- Gemini for broad web-grounded comparisons
- Perplexity for fast citation-heavy search passes
- Brave / search APIs for broader web discovery

Use outside engines for cross-checking and candidate discovery, but keep official-source verification and deterministic execution inside Roi Snips.
