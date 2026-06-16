# Daily Catalyst Hunter Foundation (2026-04-15)

Source accepted from operator on 2026-04-15 as foundational research architecture for Roi Snips stock-picking research.

## Status
Adopted as the default research foundation for catalyst discovery, candidate verification, and final ranking.

## Core adopted principles
- Broad surface scanning, narrow final selection
- Official sources first
- Structured sources second
- Social as acceleration/penalty only
- Browser use only on survivors
- No-trade is a valid success state
- Rolling overnight-to-open process
- Tradeability overlay is mandatory
- Hidden-edge findings may enrich but not originate final conviction

## Daily pass structure to align toward
- Pass A: post-close collector
- Pass B: 4:05 a.m. ET official sweep
- Pass C: 6:05 a.m. ET filing/regulatory refresh
- Pass D: 7:05-8:20 a.m. ET tradeability + acceleration gate
- Pass E: 8:20-9:00 a.m. ET shortlist verification
- Pass F: 9:05-9:15 a.m. ET final judge packet

## Hard interpretation notes for Roi Snips
Where this runbook conflicts with existing Roi Snips hard invariants, Roi Snips hard invariants remain authoritative unless explicitly changed by the operator.

Examples:
- Existing Roi Snips live-trading contract has been updated to remove per-order human approval once live submission is armed.
- Existing Roi Snips order controls now allow direct LLM live order control, subject to deterministic guardrails.
- Existing Roi Snips long-only U.S. equity constraints remain in force.

## Practical use
Use this document as the research foundation for:
- source scouting
- candidate origination
- verification workflow
- ranking logic
- no-trade logic
- final decision packet structure

## Follow-up implementation direction
Move the current premarket/scheduler flow closer to this staged runbook over time, especially:
- overnight event ledger
- official-source timed sweeps
- explicit degraded modes
- richer verification packets
- final judge packet by 9:15 a.m. ET
