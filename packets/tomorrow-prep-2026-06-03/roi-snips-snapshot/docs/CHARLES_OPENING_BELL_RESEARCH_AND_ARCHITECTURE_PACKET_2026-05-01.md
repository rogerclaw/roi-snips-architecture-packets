# Charles Opening-Bell Research and Architecture Packet

Date: 2026-05-01
Status: detailed external-review attachment draft
Purpose: consolidate the stock-pick postmortem, preferred research prompt, architecture redesign, 9:30-entry requirements, monitoring model, and recommended research/tool stack into one detailed packet suitable for external LLM review or operator reference.

Update: this packet captured the pre-implementation redesign target. Roi Snips Opening-Drive v2 has now been implemented. Current live posture is 09:30-11:00 ET entries with `OPENING_DRIVE_LONG`, `ORB_BREAK`, and `VWAP_RECLAIM`, plus sampled sub-minute opening-drive confirmation before the first full 1-minute bar when deterministic guards pass.

---

## 1. Executive summary

The current Roi Snips system is structurally biased toward safer post-open confirmation entries and is therefore not yet optimized for the specific trading style Charles wants.

Charles wants:
- exactly one best long-only U.S. stock idea each day
- same-day to 1-3 day holding horizon
- high risk with small capital size
- preference for explosive short-term upside over stability
- strong willingness to lean into market-moving hype if supported by a real catalyst and real volume
- fast small-/mid-cap repricing candidates rather than slower large-cap quality names
- the ability to evaluate and ideally buy at or near the opening bell if the demand is clearly real
- rapid ongoing monitoring after entry, including near-real-time interpretation of incoming market data

The pre-v2 system instead assumed:
- new entries only from 09:35 ET to 11:00 ET
- trigger family restricted to ORB_BREAK and VWAP_RECLAIM
- strong preference for post-open confirmation
- insufficient emphasis on hype-backed opening-drive continuation
- research quality that can degrade when discovery inputs are weak or live overlay data is missing

Core conclusion:
To behave more like Charles's preferred ChatGPT Pro-style high-conviction stock picker, the system needs both research changes and execution-policy changes. The single biggest gap is that the architecture can rank or monitor premarket names, but cannot yet legally or deterministically act on true opening-bell momentum because the 09:35 ET entry floor is enforced across instructions, config, and strategy logic.

---

## 2. Postmortem of the recent stock-pick failure

### 2.1 What happened
A recent stock comparison showed that the assistant's pick underperformed badly while a better candidate, MRAM, produced a much stronger fast move. Charles correctly pointed out that the chosen stock was not merely worse than MRAM; it was the wrong kind of pick for the actual objective.

### 2.2 Why the miss was serious
This was not just a minor ranking error. It exposed a deeper mismatch between:
- the system's implicit bias toward more respectable/slower names, and
- Charles's explicit goal of finding a violent short-term catalyst-driven winner.

### 2.3 What MRAM represented
MRAM matched Charles's preferred profile much better because it had:
- a fresh hard catalyst
- a catalyst stack rather than a single weak headline
- company-confirmed / SEC-grounded evidence
- strong short-term repricing potential relative to company size
- trader-friendly narrative
- strong premarket momentum and social acceleration
- a realistic possibility of an opening-drive continuation

### 2.4 What the assistant overweighted incorrectly
The losing logic overweighted:
- quality-company bias
- slower, safer setups
- more conservative interpretation of momentum risk
- avoidance of hype rather than distinguishing real hype from fake hype

### 2.5 What the assistant underweighted
The losing logic underweighted:
- primary-source catalyst strength
- catalyst stacking
- catalyst size relative to market cap
- float / scarcity / fast repricing mechanics
- early-session volume acceleration
- hype when attached to real evidence and order flow
- precise execution logic for an opening-drive continuation candidate

### 2.6 Architecture-level fault, not just judgment fault
The system also suffered from candidate/input quality issues. In prior runs, important overlay fields such as gap percentage, premarket dollar volume, and spread estimates were absent or null. When discovery or overlay quality is degraded, the final model is effectively choosing from an incomplete or distorted opportunity set.

### 2.7 Bottom-line lesson
For Charles's stated brief, the system must stop optimizing for "good stocks that might work" and instead optimize for "the single best explosive short-term setup that is still legitimate, still tradeable, and still early enough to matter."

---

## 3. What Charles actually wants from the system

Charles's desired behavior is not vague. It is now clear and repeatable.

### 3.1 Desired daily output
Each cycle should produce:
- one best stock only
- clear explanation of why it is better than the other visible gappers
- buy framework, invalidation framework, targets, and no-trade conditions
- a trading memo that feels like a high-end deep-research stock-picking answer rather than a generic watchlist

### 3.2 Desired stock profile
Preferred candidate profile:
- long-only U.S. stock or ETF, though common stocks are preferred
- high-risk, high-upside
- same-day or 1-3 day window
- fresh same-day catalyst
- ideally small-cap or mid-cap
- strong relative volume or accelerating attention
- potential for a sharp repricing move
- not just a rumor, but not necessarily fully institutional either
- hype is allowed and even desired when it is clearly producing real market behavior

### 3.3 Desired execution style
Charles wants the system to be able to:
- do heavy research before the open
- interpret purchase volume at the bell
- identify when opening demand is real rather than fake
- ideally buy at 9:30 ET if all required signals are present
- help monitor the trade quickly and actively after entry

### 3.4 Desired support behavior after purchase
Charles expects:
- rapid feedback loops
- quick interpretation of screenshots or structured market data
- immediate warnings when momentum deteriorates
- fast help deciding when to trim, exit, or hold a runner

---

## 4. Current system constraints preventing 9:30 live entry

There are multiple separate layers enforcing the current post-09:35 behavior.

### 4.1 Operating contract constraint
The current operating instructions include a hard invariant that forbids new entries before 09:35 ET.

### 4.2 Agent configuration constraint
`roi-snips/config/agent.yaml` currently sets the entry window start at 09:35 ET.

### 4.3 Strategy-family constraint
The current strategy family only allows:
- ORB_BREAK
- VWAP_RECLAIM

These triggers are inherently built around waiting for some post-open confirmation rather than acting directly on the opening print or first minute of demand.

### 4.4 Prompt and research scaffolding constraint
Deep-research and memo scaffolding also assumes a decision window keyed to 09:35-11:00 ET rather than 9:30 bell execution.

### 4.5 Why this matters
Even if the research engine finds the right stock, the current execution posture can still miss the part of the move Charles actually cares about.

---

## 5. Why Charles wants the architecture to support 9:30 buying

For the style Charles wants, the opening bell is not just noise. It is often where the edge is.

### 5.1 Opening-bell advantage in this style
Many of the most explosive catalyst names:
- gap hard premarket
- attract immediate opening demand
- can travel far before 09:35
- may already be half-done by the time a conservative ORB/VWAP-only system is allowed to act

### 5.2 What 9:30 access would capture
A true 9:30-capable system could capture:
- opening-drive continuation
- high-conviction market validation of premarket catalysts
- early retail/institutional chase behavior
- fast moves that never offer a clean 09:35-style retest

### 5.3 What must be acknowledged
Bell-entry capability increases risk materially. It requires better data, tighter controls, smaller size, stronger invalidation rules, and a new trigger model. It cannot just be achieved by changing one timestamp.

---

## 6. Required architecture changes to allow 9:30 live entries

A real 9:30 model requires coordinated policy, config, data, risk, and execution changes.

### 6.1 Policy and contract changes
Required changes:
- revise operating instructions to allow new entries at or immediately after 09:30 ET
- revise the entry-window start in `roi-snips/config/agent.yaml`
- revise any downstream assumptions that only 09:35-11:00 entries are valid

Potential approaches:
1. full replacement of the 09:35 floor with 09:30
2. hybrid rule: allow 09:30 entries only for a new opening-drive trigger family and keep 09:35+ for legacy ORB/VWAP entries

The hybrid model is safer.

### 6.2 Strategy and trigger changes
Add at least one new trigger family, for example:
- `OPENING_DRIVE_LONG`
- `BELL_CONTINUATION`
- `OPEN_AUCTION_HOLD`

Suggested trigger logic for a 9:30-capable entry:
- ticker already pre-qualified from premarket research
- fresh catalyst meets minimum evidence threshold
- premarket dollar volume exceeds floor
- opening spread stays below a strict cap
- opening print is not excessively above a reasonable chase band
- first 15-60 seconds show aggressive buy participation
- stock holds above premarket reference levels or quickly reclaims them
- first-minute structure confirms the move is being bought, not dumped

### 6.3 Data changes
A 9:30 system needs stronger live data than a post-09:35 confirmation system.

Mandatory live inputs at or near the bell:
- real-time last price
- real-time bid and ask
- quote age / freshness
- current spread in bps and percent
- opening print
- first-minute OHLCV
- premarket volume
- first-minute dollar volume
- relative volume estimate or volume pace proxy
- premarket high/low
- VWAP as soon as calculable
- halt status
- any new press release or filing update

High-value but optional inputs:
- Level 2 depth
- order-imbalance clues
- tape speed / repeated ask lifting
- social acceleration updates during the open

### 6.4 Risk-rule changes
A 9:30-entry strategy requires tighter risk rules than a 09:35 ORB/VWAP model.

Suggested bell-entry risk rules:
- smaller size than later-confirmation entries
- tighter max spread cap
- hard minimum premarket dollar volume
- hard minimum first-minute dollar volume
- max extension threshold above a premarket reference level
- automatic no-trade if the stock is too thin or spread blows out
- immediate exit rule if opening drive fails fast

Suggested fast-failure invalidation examples:
- loses opening print quickly after entry
- loses first-minute low on heavy selling
- large rejection wick plus volume fade
- immediate failure back through key premarket breakout zone
- repeated inability to hold VWAP after first reclaim

### 6.5 Execution logic changes
Needed execution behavior:
- limit-order only bell entries
- no market orders
- chase threshold enforcement
- immediate stop geometry or deterministic emergency exit logic
- careful handling of notional orders versus share-based orders depending on price and spread
- optional partial scale-in only if explicitly designed and guarded

### 6.6 Monitoring and kill-switch changes
Bell-entry trading requires more active monitoring after fill:
- faster polling interval
- quicker stale-data detection
- quicker disable-new-entries response if data quality degrades
- more aggressive flattening logic for failed opening-drive entries

---

## 7. Recommended new trigger family for 9:30 bell trading

This section proposes a concrete starting framework.

### 7.1 Trigger name
`OPENING_DRIVE_LONG`

### 7.2 Use case
For prequalified catalyst names with strong premarket momentum where Charles wants to exploit the opening drive rather than wait for a later ORB/VWAP setup.

### 7.3 Required preconditions
- long-only U.S. stock or ETF
- candidate prequalified during premarket research
- fresh hard catalyst present
- minimum source-quality threshold met
- premarket dollar volume above a minimum floor
- no fresh dilution/offering red flags
- spread acceptable for bell trading
- no stale quote or stale bar issues

### 7.4 Example opening-drive confirmation logic
Any one of the following styles could be used:

#### Style A: immediate strength hold
- opens near or above premarket breakout level
- first 15-30 seconds show aggressive buying
- spread remains below cap
- no immediate rejection below opening print
- limit entry near an orderly micro-pullback or held opening price

#### Style B: first-minute reclaim
- opens volatile
- briefly flushes but quickly reclaims open or key premarket level
- first-minute close is strong
- volume is exceptional
- limit entry on reclaim confirmation

#### Style C: first-minute expansion continuation
- first-minute candle closes near high on exceptional volume
- second-minute continuation holds above first-minute midpoint or VWAP
- entry uses controlled breakout continuation with chase cap

### 7.5 Hard no-trade conditions
- spread too wide
- opening candle is pure blowoff with no structure
- price already extended too far above logical risk anchor
- low real volume despite visual gap
- news turns questionable or catalyst quality weakens
- sudden halt or broken quote integrity

---

## 8. Distinguishing a true opening drive from a gap-and-fade trap

This is one of the most important design questions.

### 8.1 Signs of a true opening drive
- heavy real volume immediately after the open
- buyers repeatedly lift offers rather than passively wait
- price holds above key premarket level(s)
- dips are bought quickly
- spread stays manageable rather than exploding
- first-minute or second-minute candle closes strong relative to its range
- continuation is visible rather than entirely one-print-driven

### 8.2 Signs of a gap-and-fade trap
- opening pop immediately sells off with no quick reclaim
- large upper wick on first-minute candle with poor close
- spread widens sharply while price backs off
- volume is large but mostly distribution, not continuation
- price cannot stay above open or above the premarket breakout area
- failed reclaim attempts produce lower highs quickly

### 8.3 Operational implication
The system should not be coded to buy merely because a stock is up a lot. It should buy because a prequalified catalyst name shows evidence that the open is being accepted rather than rejected.

---

## 9. Research architecture recommended for Charles's style

A stronger research architecture should be hybrid, not single-pass.

### 9.1 Phase 1: broad overnight and premarket discovery
Objective:
Generate a dynamic candidate universe early, before the open.

Sources to search or normalize:
- SEC / EDGAR
- company press releases / IR pages
- earnings releases, decks, guidance revisions
- structured newswire feeds
- Alpaca or equivalent market-data gap/volume overlays
- Reddit / StockTwits / X / forums
- sector commentary / newsletters / blogs
- optional additional broad web search engines

Outputs:
- broad candidate list
- event clustering
- catalyst classification
- early evidence quality scoring
- early hype/attention acceleration clues

### 9.2 Phase 2: full deep research on top names
Full deep research is more appropriate than deep-mini when the system still needs to differentiate among multiple plausible catalyst names.

Use full deep research for:
- broad candidate comparison
- understanding whether a headline is real and material
- comparing stacked catalysts across names
- synthesizing institutional-quality and retail-quality signals together

### 9.3 Phase 3: shortlist synthesis
After narrowing to a smaller list, use a bounded comparison step.

Deep-mini is appropriate here if:
- the universe is already narrowed to 3-5 serious candidates
- the remaining task is comparison, not broad discovery
- time pressure near the open requires bounded synthesis

### 9.4 Phase 4: tradeability overlay and opening-bell readiness
Before the open and at the bell, overlay:
- premarket price action
- spread quality
- relative volume
- dollar volume
- likely liquidity zones
- no-trade warnings
- bell-readiness score

### 9.5 Phase 5: trigger-ready execution packet
Final candidate packet should include:
- plan ID
- ticker
- catalyst summary
- why it is better than other visible names
- entry framework
- stop / invalidation
- target(s)
- monitoring windows
- danger signals
- whether 9:30 bell entry is allowed or only 09:35+ continuation is allowed

---

## 10. Full deep research vs deep-mini

### 10.1 When full deep research is better
Full deep research is better when:
- the candidate universe is large
- the market has many competing gappers
- news interpretation matters a lot
- social/retail chatter must be filtered against real evidence
- the system needs help deciding which catalyst is most likely to reprice violently

### 10.2 When deep-mini is still useful
Deep-mini is still useful when:
- the universe is already narrowed
- the question is comparative rather than expansive
- time is short
- the system needs quick synthesis of a shortlist rather than a broad hunt

### 10.3 Recommended operating model
Best architecture:
- use full deep research early
- use deep-mini later for shortlist comparison only
- never rely on deep-mini alone as the entire discovery engine for Charles's preferred style

---

## 11. Recommended external LLM and search stack

The goal is not to worship one model. The goal is to combine complementary strengths.

### 11.1 ChatGPT Pro deep research
Strengths:
- strong synthesis
- broad multi-source search behavior
- good at producing decisive investment-style narratives
- often good at combining primary-source evidence with market chatter

Best use:
- broad daily stock-hunt prompt
- high-conviction single-pick answer
- external critique of the internal shortlist

### 11.2 Claude
Strengths:
- often strong at structured critique and comparative reasoning
- good at auditing logic, rubric quality, and failure modes

Best use:
- second-opinion ranking critique
- postmortem analysis
- prompt or SOP refinement

### 11.3 Gemini
Strengths:
- broad web-grounded perspectives
- good supplemental external search and comparison

Best use:
- parallel research comparison
- surfacing additional coverage on candidates

### 11.4 Perplexity
Strengths:
- fast citation-heavy web search style
- good for quickly surfacing current discussions and coverage

Best use:
- fast evidence gathering
- finding additional mentions, commentary, or coverage gaps

### 11.5 Brave / web search APIs
Strengths:
- broad web retrieval
- useful for discovery and cross-checking source coverage

Best use:
- finding coverage not present in structured financial feeds
- fast supplemental discovery

### 11.6 Official primary sources remain mandatory
No external LLM should replace:
- SEC / EDGAR
- company IR / press releases
- earnings releases and guidance
- official broker/data responses

### 11.7 Recommended model stack summary
Best combined approach:
- internal deterministic research system for structured discovery + guards
- full deep research for broad high-conviction ranking
- deep-mini for final shortlist comparison
- optional Claude / Perplexity / Gemini cross-checks for critique and discovery depth

---

## 12. Charles's preferred prompt, preserved as a durable reference

The preferred prompt is already stored separately, but the essence is:
- exhaustive high-depth search
- one best stock only
- decisive high-conviction answer
- prioritize catalyst + sentiment + technical setup + sharp near-term move potential
- accept high risk
- emphasize premarket/early-session behavior, volume, float dynamics, technical structure, crowding vs early, and invalidation
- output exact buy, target, invalidation, monitoring, sell triggers, and execution-risk guidance

This prompt shape should remain preserved rather than abstracted away.

---

## 13. Recommended prompt chain for better daily picks

A single prompt can work, but a prompt chain is better.

### 13.1 Step 1: broad candidate hunt
Ask for:
- top catalyst-driven U.S. stock candidates today
- primary catalyst source for each
- why the move could continue
- market cap / float / scarcity notes
- early crowding vs still-early assessment
- risk of dilution or trap behavior

### 13.2 Step 2: shortlist comparison
Feed only the best 3-5 names into a second prompt and ask:
- which single candidate is best for a same-day to 1-3 day high-risk long
- why it beats the others
- what invalidates it fastest

### 13.3 Step 3: execution packet
Ask for:
- entry range
- no-chase zone
- first target
- extension target
- thesis-break level
- opening-bell behavior to watch
- fast exit signals

### 13.4 Step 4: post-entry monitoring support
After purchase, supply structured market data and ask:
- is momentum strengthening or weakening
- trim / hold / exit implication
- what specific level matters next

---

## 14. Proposed ranking rubric to avoid missing names like MRAM again

Suggested weights for Charles's style:

1. Primary-source catalyst strength - 25%
2. Catalyst stack strength - 20%
3. Repricing potential relative to market cap / float - 15%
4. Premarket volume / RVOL / opening-drive readiness - 15%
5. Social acceleration / hype that appears real - 10%
6. Technical tradeability and invalidation clarity - 10%
7. Execution quality / spread / liquidity - 5%

### 14.1 Positive scoring examples
Score up when:
- official contract / approval / earnings beat / guide-up / partnership exists
- headline is material relative to company size
- premarket volume is real
- narrative is easy for traders to chase
- stock still looks early enough to matter

### 14.2 Negative scoring examples
Score down when:
- catalyst is vague or rumor-only
- name is already obviously exhausted
- spread is broken
- likely dilution risk exists
- it is merely a slow large-cap move with limited near-term asymmetry

---

## 15. Post-entry monitoring model for Charles's preferred style

Charles wants very rapid support after purchase, especially for fast-moving winners.

### 15.1 Monitoring cadence
#### Sub-minute / every few seconds if possible
Watch:
- last price
- bid/ask
- spread
- whether buyers keep lifting offers
- whether price is holding above open / VWAP / first pivot
- whether the move looks orderly or unstable

#### Every 1 minute
Watch:
- candle close quality
- volume versus prior minute
- higher-high / higher-low structure
- failed breakout attempts
- wick size and rejection behavior
- momentum acceleration or decay

#### Every 5 minutes
Watch:
- whether the trade is following through or stalling
- whether broader intraday structure still supports the original thesis

### 15.2 Best input format from Charles
Most useful manual input format:
- ticker
- time
- last
- bid
- ask
- spread
- open
- high
- low
- current volume
- first-minute candle OHLCV
- current 1-minute candle OHLCV
- VWAP
- premarket high
- premarket low
- any new headlines

Screenshots help, but structured text is faster and safer for decision support.

### 15.3 Profit-taking logic for this style
Because the objective is big quick wins:
- take partial profits into the first obvious expansion zone
- keep only a smaller runner if volume confirms continuation
- do not let a fast winner fully round-trip if momentum clearly breaks

### 15.4 Danger signals requiring fast caution or exit
- loses opening drive
- fails at VWAP and cannot reclaim
- lower high after first thrust
- volume falls off a cliff after the spike
- spread widens badly
- fresh dilution/offering headline appears
- halt risk or broken quotes

---

## 16. Suggested improvements to the master SOP

The master SOP should explicitly cover:
- user objective and style preference
- daily research phases
- full deep research vs deep-mini usage policy
- catalyst/hype ranking rubric
- 9:30-specific trigger spec
- post-entry monitoring support loop
- screenshot-reading accuracy requirement
- change-management and versioning for prompts

The SOP should remain a living document rather than a static note.

---

## 17. Implementation roadmap

### 17.1 Immediate documentation actions
Already completed:
- preserved Charles's preferred prompt
- created master stock-pick SOP
- created external research email draft
- updated candidate and final memo prompts to better match the desired style

### 17.2 Next technical actions
1. add full deep-research premarket pass
2. separate broad discovery from shortlist comparison
3. add bell-readiness score and required live overlay fields
4. design and document `OPENING_DRIVE_LONG` trigger
5. decide whether to keep 09:35 floor or explicitly authorize 9:30 bell entries
6. if 9:30 entries are authorized, patch policy/config/risk/trigger layers together
7. add rapid post-entry monitoring packet format for manual operator updates

### 17.3 Safety recommendation
If 9:30 buying is adopted, roll it out in stages:
- stage 1: read-only bell scoring
- stage 2: paper bell-entry simulation
- stage 3: tiny-size live bell entries with strict hard stops and kill switch

---

## 18. Key final conclusion

Charles wants a system that is materially more aggressive, more hype-aware, faster to act, and better aligned with small-cap catalyst continuation trading at the open.

That does not mean chasing garbage blindly. It means:
- better discovery
- better prompt design
- better scoring
- better live data
- better opening-bell trigger logic
- faster post-entry monitoring
- and explicit permission to act before 09:35 if the architecture is redesigned safely

The current system can move substantially closer to this goal, but a true 9:30-capable version requires deliberate rule changes rather than minor prompt tuning.

---

## 19. Reference files already created

- `roi-snips/prompts/CHARLES_HIGH_CONVICTION_STOCK_PROMPT_V2026-05-01.md`
- `roi-snips/docs/MASTER_STOCK_PICK_SOP.md`
- `roi-snips/docs/CHARLES_GPT_PRO_RESEARCH_EMAIL_2026-05-01.md`
- `roi-snips/docs/CHARLES_OPENING_BELL_RESEARCH_AND_ARCHITECTURE_PACKET_2026-05-01.md`

---

## 20. Suggested external review request

Recommended next step:
Take this packet and the preserved preferred prompt to a high-end external research model and ask it to produce:
- an improved architecture
- a better prompt chain
- a model/tool stack recommendation
- a detailed 9:30-entry ruleset
- a daily monitoring checklist
- and a critique of whether the proposed opening-drive logic is aggressive enough without becoming undisciplined garbage-chasing
