# Roi Snips Architecture Packets

Sanitized architecture and validation packet for ChatGPT review.

Generated: 2026-05-27 08:26 PT

## Contents

- `reports/implementation/ROI_SNIPS_SHELL_CAPABLE_SHADOW_VALIDATION_HARDENING_2026-05-27.txt`
  - Follow-up implementation report for the shell-capable crontab/canary hardening.
- `reports/implementation/ROI_SNIPS_MORNING_FAILURE_AUDIT_REPORT_2026-05-27.txt`
  - Full incident audit for the failed 2026-05-27 morning validation handoff.
- `reports/implementation/ROI_SNIPS_OPTIMIZED_RESEARCH_IMPLEMENTATION_REPORT_2026-05-26.txt`
  - Implementation report for the optimized research runbook pass.
- `ops/progress/ACTIVE.md`
  - Sanitized current implementation ledger, including the remaining scheduled-proof caveat.
- `source-packets/Roi_Snips_Optimized_Research_Implementation_Runbook_OpenClaw.txt`
  - Source runbook that drove the implementation.
- `scripts/run_next_open_shadow_validation.py`
  - Sanitized copy of the no-order shadow validation wrapper patched during the incident response.
- `scripts/run_shell_capable_shadow_validation.sh`
  - Shell-capable canary + validation wrapper now scheduled from local crontab.
- `tests/test_no_order_validation.py`
  - Regression coverage for no-order / brokerless validation behavior.
- `tests/test_post_audit_fix_directive.py`
  - Post-audit regression coverage for source lanes, stream-required validation, and replay proof.
- `ops/crontab/ROI_SNIPS_SHELL_SHADOW_VALIDATION.cron`
  - Sanitized crontab block for the shell-capable 06:35 PT weekday proof.
- `reports/live_monitor/next_open_shadow_validation_2026-05-27.json`
  - Latest clean post-patch validation summary.
- `reports/live_monitor/runs/opening_stream_2026-05-27_151215/final_summary.json`
  - Fresh no-order stream proof.
- `reports/live_monitor/runs/opening_stream_2026-05-27_163743/final_summary.json`
  - Fresh shell-capable-wrapper no-order stream proof.
- `reports/live_monitor/shell_capable_shadow/canary_20260527T163626Z.json`
  - Shell-capable wrapper canary artifact.
- `reports/live_monitor/shell_capable_shadow/validation_20260527T163626Z.log`
  - Shell-capable wrapper validation log.
- `reports/morning/json/2026-05-27.json`
  - Same-day research packet used for validation.
- `reports/morning/md/2026-05-27.md`
  - Markdown rendering of the same-day research packet.
- `reports/morning/json/2026-05-26_runbook_proof.json`
  - Local runbook-proof morning packet generated during the implementation pass.
- `reports/morning/md/2026-05-26_runbook_proof.md`
  - Markdown rendering of the local runbook-proof morning packet.
- `runs/2026-05-26-runbook-proof/meta/run_manifest.json`
  - Runbook-proof artifact manifest.
- `runs/2026-05-26-runbook-proof/normalized/source_lane_status.json`
  - Source-lane status proof artifact.
- `runs/2026-05-26-runbook-proof/normalized/daily_best_pick_packet.json`
  - Final best-pick packet proof artifact.
- `reports/live_monitor/runs/runbook_stream_replay_2026-05-26/final_summary.json`
  - Captured-tape stream replay proof summary.
- `reports/live_monitor/runs/runbook_continuation_replay_2026-05-26/final_summary.json`
  - Continuation replay proof summary.
- `reports/live_monitor/runs/runbook_continuation_replay_2026-05-26/continuation_replay_summary.json`
  - Continuation replay detail summary.

## Sanitization Boundary

This repo intentionally excludes:

- OpenClaw workspace memory and user profile files.
- `.env` files and credentials.
- Broker/account/order/position raw payloads beyond the post-patch validation summary.
- STR, personal messages, calendar, email, and unrelated operational data.
- Local logs and caches.
- Raw JSONL tape dumps; only compact proof summaries are included.

## Current Validation Snapshot

Latest shell-capable-wrapper no-order validation:

- `status=OK`
- `orders_allowed=false`
- `orders_submitted=false`
- `broker_account_inspected=false`
- `broker_orders_inspected=false`
- `broker_positions_inspected=false`
- streamed symbols: `INFQ`, `NVDA`, `TSLA`
- `raw_quote_count=3992`
- `raw_trade_count=5358`
- `decision_count=9350`
- `proposal_count=0`

Scheduled acceptance caveat:

- The shell-capable crontab block was installed after the 2026-05-27 06:35 PT slot.
- The manual shell-capable proof passed.
- The scheduled 06:35 PT weekday proof remains pending until the next eligible crontab run.

## Notes For Review

The audit report is the primary starting point. The key architectural lesson is that a scheduled job existing is not enough; future morning readiness needs a shell-capable canary and a produced validation artifact before being called ready.
