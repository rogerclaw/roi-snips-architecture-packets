# Roi Snips Morning Report

Generated: 2026-05-27T03:26:21.130857+00:00
Status: degraded

## Market session
- is_open=False same_day_session_ahead=False next_open=None

## Best pick candidate
- none

## Candidate roles
- research_leader=INFQ anti_chase_state=SECOND_LEG_WATCH lifecycle=SECOND_LEG_WATCH entry_viability=42
- executable_primary=None
- second_leg_watch:
  - INFQ anti_chase_state=SECOND_LEG_WATCH gap_pct=55.0 hyper=8.7
- same_style_backup_pool_ok=True reason=None
- same_style_non_megacap_backups=MRAM, ABEO, BBAI
- backup_pool_diagnostics:
  - same_style_candidates_selected=MRAM, ABEO, BBAI
  - mega_cap_backups_used=none
  - reason_mega_cap_backup_used=None
  - source_lane_failures_affecting_backups=none

## Governed best-pick memo
- source_mode=internal_fallback route=None best_pick=None
- research_leader=INFQ

## Candidate research packets
- INFQ | validation=primary_confirmed | confidence=medium_high | hyper=8.7
  - thesis=INFQ receives federal funding award
  - market gap=55.0 premarket_dollar_volume=10000000 spread=None
  - why_asymmetric=Fresh same-day or near-same-day catalyst.; Government funding/contract catalysts can create a simple high-beta narrative.; Premarket dollar volume is large enough to show real tape confirmation.
  - why_wrong=Spread estimate is missing.; Large premarket gap may already price in the catalyst.
  - trade_gate_pass=False blockers=none
- MRAM | validation=structured_confirmed | confidence=medium | hyper=4.2
  - thesis=MRAM wins contract
  - market gap=16.0 premarket_dollar_volume=2000000 spread=None
  - why_asymmetric=Fresh same-day or near-same-day catalyst.; Premarket dollar volume is large enough to show real tape confirmation.
  - why_wrong=Spread estimate is missing.
  - trade_gate_pass=False blockers=none

## A-tier
- none

## B-tier
- none

## C-tier
- none

## No-trade list
- INFQ: SECOND_LEG_WATCH until continuation confirms

## Source status
- runbook_proof: ok=True count=1 reason=synthetic local artifact proof

## Source lane status
- Alpaca SIP: configured=True ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=none errors=none
- Alpaca News: configured=True ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=none errors=none
- Benzinga: configured=True ran=True produced_candidates=1 useful_evidence=1 useful_for_primary=False affected_backup_list=True missing_credentials=none errors=none
- SEC EDGAR: configured=True ran=True produced_candidates=1 useful_evidence=1 useful_for_primary=True affected_backup_list=False missing_credentials=none errors=none
- Company IR: configured=True ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=none errors=none
- FMP movers: configured=False ran=True produced_candidates=1 useful_evidence=1 useful_for_primary=False affected_backup_list=True missing_credentials=FMP_API_KEY errors=none
- StockTwits: configured=False ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=STOCKTWITS_ACCESS_TOKEN,STOCKTWITS_BEARER_TOKEN errors=none
- TradingView-style screener: configured=False ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=ROI_SNIPS_ENABLE_TRADINGVIEW_SCREENER errors=none
- Grok/X: configured=False ran=True produced_candidates=1 useful_evidence=1 useful_for_primary=False affected_backup_list=True missing_credentials=XAI_API_KEY,GROK_API_KEY errors=none
- Reddit: configured=True ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=none errors=none
- Tavily/Brave/Exa: configured=False ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=TAVILY_API_KEY,BRAVE_API_KEY,EXA_API_KEY errors=none
- Firecrawl/Crawl4AI: configured=False ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=FIRECRAWL_API_KEY errors=none
- openFDA: configured=False ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=OPENFDA_API_KEY errors=none
- ClinicalTrials.gov: configured=True ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=none errors=none
- SAM.gov/USAspending: configured=False ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=SAM_GOV_API_KEY,USASPENDING_API_KEY errors=none
- Nasdaq halt feed: configured=True ran=False produced_candidates=0 useful_evidence=0 useful_for_primary=False affected_backup_list=False missing_credentials=none errors=none
