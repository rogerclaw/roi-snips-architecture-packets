# Roi Snips Architecture Packets

Sanitized Roi Snips architecture, implementation, and validation packets for ChatGPT/GitHub review.

This repository is the review-friendly packet surface. The fuller sanitized code/config/test repository is private at `rogerclaw/roi-snips`.

## ChatGPT Pro Start Point

Begin with:

- `CHATGPT_PRO_ROI_SNIPS_START_HERE.md`
- `source-packets/2026-05-31-hybrid-deep-mini-primary-restore/ROI_SNIPS_HYBRID_DEEP_MINI_PRIMARY_RESTORE_ACTION_PLAN_2026-05-31.md`
- `source-packets/2026-05-31-hybrid-deep-mini-primary-restore/reports/implementation/ROI_SNIPS_HYBRID_GROK_HEAT_DEEP_MINI_PRIMARY_RESTORE_2026-05-31.txt`
- `packets/chatgpt-review-20260529T193459Z/MANIFEST.md`

If ChatGPT Pro has access to the private repo, also read `rogerclaw/roi-snips` branch `codex/hybrid-main-repo-sync`, especially `docs/CHATGPT_PRO_GITHUB_PLUGIN_START_HERE.md`.

## Current Architecture Snapshot

The current intended architecture is the May 31 hybrid restore:

- Grok/X supplies social heat, velocity, thread context, quick web verification, and challenger notes.
- Governed OpenAI deep-mini/deep research is the primary live stock picker.
- Only governed OpenAI deep-mini/deep output may create a live-valid Trade Authorization Ticket.
- Deterministic code may trade only the ticket-authorized ticker.
- Final live arming must pass same-day ticket, freshness, market-data, risk, broker-state, and live guard checks.
- Grok-only candidates, deterministic fallbacks, A/B/C watchlist rows, stale prior winners, and backups are research-only unless a valid ticket explicitly authorizes them.

Older packets remain useful as incident history and regression evidence, but the May 31 hybrid restore packet is the current architecture source when documents conflict.

## Latest Packets

- `source-packets/2026-05-31-hybrid-deep-mini-primary-restore/`
  - Current hybrid Grok heat plus deep-mini primary restore.
  - Includes action plan, implementation report, config snapshots, script snapshots, and focused regression test snapshots.
- `packets/chatgpt-review-20260529T193459Z/`
  - ChatGPT review packet for ticket-gated architecture work.
- `packets/roi-snips-nvda-live-failure-2026-05-29/`
  - Sanitized failure packet for the NVDA live-path issue and ticket-boundary hardening.
- Root May 26-27 reports and validation artifacts
  - Historical morning-readiness and shell-capable validation work.

## Sanitization Boundary

This repo intentionally excludes:

- OpenClaw workspace memory and user profile files.
- `.env` files and credentials.
- Broker account/order/position raw payloads.
- STR, personal messages, calendar, email, and unrelated operational data.
- Local logs and caches.
- Raw JSONL tape dumps; only compact proof summaries are included.

Do not add live secrets, raw broker/account/order/position state, raw logs, raw transcripts, raw guest/homeowner PII, financial exports, or `.env` files to this repository.

## Validation Snapshot

The May 31 hybrid restore packet records:

- focused hybrid suite: `33 passed, 1 warning`
- full suite: `343 passed, 1 warning`
- shell syntax: `bash -n scripts/*.sh` passed
- final live arming dry-run for `2026-06-01`: `NO_GO`, no ticket, not armed
- deliberate non-actions: no broker account/order/position inspection, no order preview/place/submit/replace/cancel, no manual arming

## Review Notes

When reviewing with ChatGPT Pro, ask for file-path citations and a branch-sized patch plan. ChatGPT can analyze and draft. John/Codex should perform edits, validation, commits, pushes, and PR work.
