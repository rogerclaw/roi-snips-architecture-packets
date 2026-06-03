# Roi Snips Grok / X Search Integration Runbook

Purpose: use Grok as a social/X discovery and attention-acceleration lane for Roi Snips. Grok must feed candidate evidence into the existing research ledger, ranking, market overlay, and execution gates. It must not choose trades by itself or override official-source, liquidity, spread, session, risk, or live-trading guards.

## Current Required Inputs

- `XAI_API_KEY` configured through John's governed secret path, not pasted into chat or committed to disk.
- Exact xAI model ID selected by John and recorded in config; prefer a stable alias/model currently supported by xAI.
- Confirmation that xAI Responses API tool access works for:
  - `x_search`
  - `web_search`
  - citations / sources returned in responses
- Roi Snips local market data remains Alpaca SIP; verified working after Algo Trader Plus upgrade.
- Roi Snips live entries remain disabled until Charles explicitly arms trading.

## Current Status As Of 2026-05-20

- OpenClaw has `xai/grok-4.3` configured with alias `grok`.
- John previously confirmed the xAI plugin/provider is enabled and OpenClaw config validates.
- A live one-shot `xai/grok-4.3` call now succeeds.
- OpenClaw `web.search` provider `grok` is configured and available.
- A Grok web-search smoke test returned X/cashtag citations, confirming Grok can be used for X-oriented discovery queries.
- Treat Grok as usable for manual/scout research now. Roi Snips also has a first structured integration via `src/adapters/grok_search.py` and `src/research/scouts/social_scout.py`; it emits social-only `grok_x_search` raw events with citations. This is enough for discovery/ranking input, but still needs more tuning before it should be considered a mature production social-alpha lane.

## xAI Tool Facts To Encode

Official docs checked 2026-05-20:

- Web Search: `https://docs.x.ai/developers/tools/web-search`
- X Search: `https://docs.x.ai/developers/tools/x-search`
- Models: `https://docs.x.ai/developers/models`

xAI docs show Grok can use:

- `web_search` for real-time web search and page browsing.
- `x_search` for keyword search, semantic search, user search, and thread fetch on X.
- `allowed_x_handles`, `excluded_x_handles`, `from_date`, and `to_date` filters for X search.
- citations/sources in responses; Roi Snips should persist these as evidence links.

## John Handoff Contract

John should provide Roi Snips with a small, structured scout response. Do not hand Roi Snips a prose-only answer.

Required JSON fields:

```json
{
  "generated_at_utc": "ISO-8601",
  "model": "xai model id",
  "tools_used": ["x_search", "web_search"],
  "query_window": {
    "from_date": "YYYY-MM-DD or null",
    "to_date": "YYYY-MM-DD or null"
  },
  "candidates": [
    {
      "ticker": "SYMBOL",
      "company_name": "optional",
      "claim_summary": "short catalyst/social claim",
      "attention_signal": "what changed on X/social",
      "evidence_urls": ["source/citation URLs"],
      "x_handles_or_threads": ["handles/thread URLs if available"],
      "confidence": 0.0,
      "red_flags": ["hype-only", "stale", "unclear ticker", "possible pump"]
    }
  ]
}
```

## Acceptance Rules

- A Grok/X candidate is discovery evidence only until another lane confirms it.
- Social-only candidates may enter the research universe but must be blocked from executable best-pick status unless official or structured evidence confirms the catalyst.
- Persist Grok citations, query text, response JSON, and model/tool metadata under the run artifact directory.
- Reject or down-rank candidates with unclear ticker mapping, stale chatter, no verifiable source, or obvious pump language.
- Never let Grok text directly populate an order plan.

## Validation Steps

1. Secret presence check only: confirm `XAI_API_KEY` is present without printing it.
2. Tool smoke: run a harmless `x_search` or Grok-backed `web.search` query and verify citations/sources are returned.
3. Schema smoke: convert one Grok response into the JSON contract above.
4. Pipeline smoke: inject candidates into Roi Snips discovery artifacts and verify ranking/gates handle them.
5. Safety smoke: verify a social-only candidate is not executable without official/structured confirmation.
6. Full tests: run `PYTHONPATH=. .venv/bin/pytest tests`.
7. Readiness check: run `scripts/check_live_readiness.sh`; live entries should stay disabled unless Charles explicitly arms them.

## Current Implementation

- `src/adapters/grok_search.py` calls OpenClaw `infer web search --provider grok --json`, keeping xAI credentials in OpenClaw auth rather than Roi Snips `.env`.
- `src/research/scouts/social_scout.py` uses the Grok adapter and emits `source_name=grok_x_search` events.
- These events are `social_flag=true`, `official_flag=false`, and `structured_flag=false`, so existing execution gates block them from executable status unless other lanes confirm the catalyst.
- `config/workflow.yaml` lists `grok_x_search` as optional and non-blocking.

## Open Items

- Tune query templates for premarket small-cap catalyst discovery.
- Decide whether John remains the xAI credential owner while Roi Snips owns the adapter, or whether John should periodically pass structured JSON to Roi Snips.
- Add richer persistence for full Grok response JSON beyond raw event notes if later audit requirements justify it.
