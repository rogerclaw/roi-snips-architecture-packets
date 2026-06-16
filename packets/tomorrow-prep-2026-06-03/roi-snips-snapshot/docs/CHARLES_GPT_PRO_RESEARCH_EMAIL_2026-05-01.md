Subject: Need architecture redesign for high-risk opening-bell stock picker/executor

Update: this redesign has now been implemented as Roi Snips Opening-Drive v2. The current runtime supports 09:30-11:00 ET entries with `OPENING_DRIVE_LONG`, `ORB_BREAK`, and `VWAP_RECLAIM`; the notes below remain useful as the original external-review brief.

I am building a long-only U.S. stock trading assistant for small, high-risk, same-day to 1-3 day momentum trades. I want explosive short-term upside, not safer slow movers. I use Webull and I am comfortable with a very small amount of capital at high risk. I want the system to behave more like a top-tier ChatGPT Pro deep-research stock picker and much less like a conservative watchlist generator.

What I want:
- exactly one best stock to buy today, not a generic watchlist
- strong preference for fresh catalysts, small/mid-cap repricing potential, high relative volume, retail hype, and opening-drive continuation
- a system that is willing to lean more toward hype when hype is clearly market-moving and backed by enough evidence
- heavy premarket research so it is ready before the open
- the ability to evaluate purchase volume and price action at the bell
- ideally the ability to buy at or very near 9:30 ET if the opening demand is clearly strong
- rapid ongoing monitoring after entry so I can decide when to sell almost in real time

Recent failure example:
- The assistant picked the wrong kind of stock and missed a much better fast-moving small-cap winner.
- A better pick (MRAM) had a stacked catalyst: contract + earnings beat + guidance upside + small-cap momentum.
- The assistant overweighted safer/quality bias and underweighted catalyst-stack strength, market-cap asymmetry, float dynamics, and hype acceleration.
- I want the architecture tuned toward finding these fast-opening momentum winners earlier and ranking them correctly.

Former blockers in the pre-v2 system:
- It had been hard-coded for new entries only from 09:35 ET to 11:00 ET.
- It had centered the valid trigger family on ORB_BREAK and VWAP_RECLAIM after 09:35.
- It is too cautious about hype and too slow to exploit an opening drive if heavy volume is obvious at 9:30.
- It appears to use deep-mini in places where full deep research may be better for broad discovery.
- It can fail to get enough high-signal external inputs compared with ChatGPT Pro.

I want you to help redesign the architecture.

Please answer these questions in depth:

1. How should I redesign the research workflow so that it behaves more like the best ChatGPT Pro deep-research stock picker for same-day/1-3 day explosive upside?

2. What is the best hybrid architecture for:
- broad overnight/premarket discovery
- deep research on top candidates
- bell/opening-drive confirmation
- rapid post-entry monitoring
- final sell-signal support

3. Should I use full deep research instead of deep-mini for the early discovery step? If so, where exactly should full deep research be used, and where is deep-mini still appropriate?

4. What other LLMs, search engines, or research tools should I combine with ChatGPT Pro-like outputs to improve candidate quality? Compare ChatGPT Pro deep research, Claude, Gemini, Perplexity, Brave/web search, and any other strong choices.

5. What exact research prompt or multi-step prompt chain should I use to maximize the chance of finding the kind of stock I want: fast, volatile, catalyst-driven, small/mid-cap, high-hype, high-volume, big opening move potential?

6. If I want the system to buy at 9:30 ET instead of waiting until 9:35 ET, what exact architectural, risk, and execution-rule changes should I make? I want specifics, including:
- what trigger family should replace or supplement ORB/VWAP-only logic
- what volume/spread/liquidity rules are needed to avoid garbage entries
- how to distinguish a true opening drive from a gap-and-fade trap
- what data is mandatory at the bell
- what stop/exit logic is needed for a 9:30 entry model

7. How should the system monitor the stock after purchase if I want very rapid updates and almost real-time sell help? What exact inputs should I feed it every few seconds or every minute?

8. What ranking model should it use so it does not miss names like MRAM again? I want the scoring to favor:
- fresh hard catalyst
- catalyst stack
- small/mid-cap asymmetry
- float scarcity / squeeze potential if relevant
- unusual volume / RVOL
- social acceleration / hype when real
- still-early story versus exhausted move
- clear invalidation levels and execution practicality

Here is the exact stock-picking prompt I currently like best:

I am looking to make a stock investment today just after market open, with the intention of selling the same day or within a couple of days. I want you to conduct an exhaustive, high-depth search across all relevant resources you can access, including financial news, company press releases, SEC filings, earnings materials, analyst commentary, trading blogs, market newsletters, Reddit threads, stock forums, X sentiment, Motley Fool, and any other credible or high-signal sources available to ChatGPT Pro. Treat this as if I am consulting one of the best stock pickers in the world for a high-conviction short-term trade.

I do not want a generic watchlist. I want you to identify the single best short-term stock opportunity for today based on the strongest combination of catalyst, sentiment, technical setup, and probability of a sharp near-term move. Do deep research, think carefully, and synthesize both institutional-quality signals and retail sentiment to find something volatile that is expected to have a massive short-term uptick due to key progress, approval, product launch, merger, acquisition, partnership, contract award, earnings surprise, guidance revision, short squeeze potential, unusual volume, sector momentum, or another material catalyst.

I am completely fine with high risk; this will be a very small investment, so I am able to tolerate maximum risk. I am not a professional day trader and use Webull.

In your analysis, weigh:
- current news flow and catalyst strength
- sentiment across retail and professional channels
- premarket or early-session trading behavior if available
- unusual volume, momentum, float dynamics, and short-interest conditions if relevant
- technical levels such as support, resistance, breakout levels, gap fills, and likely liquidity zones
- whether the move is already overcrowded or still early
- what could invalidate the trade quickly

For the final answer, give me:
- The single best stock to buy today
- Ticker and company name
- The exact reason it could move sharply in the next hours or days
- The underlying catalyst and why the market may not have fully priced it in yet
- Evidence from the research you reviewed, including sentiment and discussion trends
- A suggested limit buy price or buy range
- A realistic upside target for same-day and 1-3 day scenarios
- A downside level or clear risk threshold where the thesis is broken
- What timeframes I should monitor most closely after entry
- Specific sell triggers, including both profit-taking and danger signals
- A brief note on execution risk for someone using Robinhood with basic tools

Prioritize asymmetric upside and high-conviction setups over safer, lower-volatility names. I care more about explosive short-term potential than stability. Be decisive, ranking quality of evidence over hype, but do not ignore hype if it is clearly becoming a market-moving force.

Please give me:
- a full redesigned architecture
- an improved master SOP
- a recommended model/tool stack
- a prompt chain
- a scoring rubric
- a 9:30-entry ruleset
- a post-entry monitoring checklist
- and an explanation of how to make the system much better at catching fast opening-bell winners without becoming pure garbage-chasing.
