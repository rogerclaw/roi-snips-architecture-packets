# Roi Snips Clean Rebuild Anti-Stall Note - 2026-05-28

## What Happened

Charles was right to call out repeated apparent stalls during the clean rebuild. The work kept getting interrupted while the live chat turn was still in the "scan and plan" phase, so the visible surface showed promises and status updates instead of shipped patches and proof.

## Root Causes

1. The task was too large for one live chat turn. Treating the entire clean rebuild as one implementation unit made interruptions expensive.
2. The first actions were broad repo scans. That consumed turn time and context before a useful patch landed.
3. Workspace git status is noisy because `roi-snips` is an untracked project under a much larger OpenClaw workspace. Unbounded status/list commands create huge output and slow the task.
4. The live Telegram lane is fragile for long code passes. User interruptions and OpenClaw context maintenance abort the current turn; any uncommitted reasoning in the model is lost.
5. The progress ledger existed, but it recorded next commands more than small acceptance slices. It did not force "patch first, verify immediately" behavior.
6. User-facing updates were too intention-heavy. They explained what would happen before enough code/proof existed.

## New Operating Rules For This Rebuild

1. Ship in slices that can survive interruption:
   - slice 1: hard no-false-readiness clean rebuild foundation
   - slice 2: required prompt pack and schema files
   - slice 3: source-breadth and same-style backup integration into the morning report path
   - slice 4: event-timed strategy and continuation/opening routing expansion
   - slice 5: implementation report and GitHub publication
2. For each slice, edit first once enough local context is known, then run focused tests, then update this ledger.
3. Keep commands bounded to `/Users/rogerclaw/.openclaw/workspace/roi-snips`; do not run broad workspace-root status/listing commands.
4. Use `git status --short --untracked-files=all -- <specific paths>` or explicit path lists, not whole-workspace status.
5. After every user interruption, resume from `ops/progress/ACTIVE.md` and this anti-stall note, not from transcript memory.
6. Never send "moving into edits" twice without a patch/test result in between.
7. Do not call the rebuild done until focused rebuild tests, full test suite, CLI/artifact smoke, implementation report, and GitHub publication are complete.

## Verified Slice State, Not Full Runbook Completion

As of 2026-05-28 12:50 PT, the brokerless clean-rebuild source-of-truth slice is complete locally. As of the 13:01 PT audit, the full attached clean rebuild runbook is not complete.

- `src/ops/artifact_gate.py`
- `src/research/war_room.py`
- `src/strategy/momentum_router.py`
- `src/workflows/clean_rebuild.py`
- `scripts/run_clean_rebuild_shadow.py`
- `docs/prompts/rebuild/CHATGPT_PRO_RESEARCH_WAR_ROOM.md`
- `docs/prompts/rebuild/00_MASTER_MISSION.md` through `15_POST_MISS_AUDIT.md`
- `tests/test_clean_rebuild.py`
- `reports/implementation/ROI_SNIPS_CLEAN_REBUILD_IMPLEMENTATION_REPORT_2026-05-28.txt`

Verification:

- Focused: `PYTHONPATH=. .venv/bin/pytest tests/test_clean_rebuild.py tests/test_no_order_validation.py -q` -> `10 passed`
- Full: `PYTHONPATH=. .venv/bin/pytest -q` -> `189 passed, 1 pre-existing websockets deprecation warning`
- Brokerless CLI smoke: `ready=true`, no missing artifacts, no blockers, no warnings, `primary_mode=OPENING_BURST_HYPER_LONG`, `broker_action=NONE`, no-order attestation true.

No broker account/order/position state was inspected, no orders were placed/previewed/replaced/canceled, and no guard files were armed or mutated.

## Completion Boundary

Only the brokerless source-of-truth/control-plane slice is complete. The full runbook still requires the missing exact-path morning control plane, canary/readiness scripts, true broad discovery/source-breadth modules, strategy modules, workflow modules, and focused tests from Sections 10 and 11.

13:01 PT exact-path audit: 49 required source/script/test files listed in the attached runbook, 4 present, 45 missing. Do not answer "all done" for the full runbook until those are implemented or intentionally mapped to equivalent existing files with tests.

## Process Fix

The specific stall pattern was not "no files changed"; it was "the live chat lost its execution thread before the user saw proof." Going forward for long implementation work:

1. First durable action is a minimal patch or a clear blocker, not a broad repo survey.
2. Every patch slice must end with a focused test result and an `ACTIVE.md` update.
3. If interrupted, resume from `ACTIVE.md` and the task-specific anti-stall note before sending any new plan.
4. Do not send intention-only status updates after the first one; send proof, blocker, or say a command is actively running.
5. Keep one authoritative task state file current so transcript compaction cannot make the task appear lost.
