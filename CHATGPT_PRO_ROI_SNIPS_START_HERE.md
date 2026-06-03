# ChatGPT Pro Roi Snips Start Here

Use this file as the first prompt anchor when asking ChatGPT Pro to review Roi Snips architecture through GitHub.

## Repositories To Connect

Grant ChatGPT GitHub access to:

- `rogerclaw/roi-snips`
  - private sanitized full code/config/test/docs repo
  - current review branch: `codex/hybrid-main-repo-sync`
  - active PR: `https://github.com/rogerclaw/roi-snips/pull/2`
- `rogerclaw/roi-snips-architecture-packets`
  - public sanitized architecture and validation packet repo
  - current branch: `main`

If a repo does not appear in ChatGPT after connecting GitHub, open GitHub search and search `repo:rogerclaw/roi-snips import` or `repo:rogerclaw/roi-snips-architecture-packets import`, then wait several minutes for indexing.

## Capability Boundary

ChatGPT Pro with GitHub can read, search, analyze, and cite repository content. It should draft architecture findings and proposed changes.

John/Codex remains responsible for:

- branch creation
- file edits
- validation
- commits
- pushes
- pull requests
- deployment proposals
- live runtime work

Do not treat ChatGPT text as deployed behavior.

## Current Architecture To Review

The current intended Roi Snips architecture is:

```text
deterministic catalyst discovery
-> evidence ledger
-> Grok/X heat, social velocity, thread context, and challenger notes
-> governed OpenAI deep-mini/deep primary stock-picker pass
-> one valid Trade Authorization Ticket or NO_TRADE
-> deterministic final live arming gate
-> opening monitor constrained to the ticket-authorized ticker
-> order router constrained by market, risk, broker, and live guards
```

Key boundary:

- Grok/X can discover and challenge.
- Grok/X cannot be the final live selector.
- Grok/X cannot create a live-valid ticket.
- Grok/X cannot authorize backups.
- Grok/X cannot override deep-mini/deep.
- Grok/X cannot approve or place orders.
- Deterministic fallback is research-only.
- No valid same-day ticket means no live or paper entry.

## Read Order

In `rogerclaw/roi-snips-architecture-packets`:

1. `README.md`
2. `CHATGPT_PRO_ROI_SNIPS_START_HERE.md`
3. `source-packets/2026-05-31-hybrid-deep-mini-primary-restore/ROI_SNIPS_HYBRID_DEEP_MINI_PRIMARY_RESTORE_ACTION_PLAN_2026-05-31.md`
4. `source-packets/2026-05-31-hybrid-deep-mini-primary-restore/reports/implementation/ROI_SNIPS_HYBRID_GROK_HEAT_DEEP_MINI_PRIMARY_RESTORE_2026-05-31.txt`
5. `source-packets/2026-05-31-hybrid-deep-mini-primary-restore/source-snapshots/`

In `rogerclaw/roi-snips` branch `codex/hybrid-main-repo-sync`:

1. `README.md`
2. `docs/CHATGPT_PRO_GITHUB_PLUGIN_START_HERE.md`
3. `docs/architecture/RESEARCH_TO_EXECUTION_TICKET_BOUNDARY.md`
4. `docs/architecture/DEPRECATED_PATHS.md`
5. `config/workflow.yaml`
6. `configs/live.yaml`
7. `scripts/run_live_trade_ready_premarket.sh`
8. `scripts/run_final_live_arming_gate.sh`
9. `src/workflows/research_pipeline.py`
10. `src/workflows/grok_research_pipeline.py`
11. `src/workflows/final_live_arming_gate.py`
12. `src/workflows/live_monitor.py`
13. `src/execution/order_router.py`
14. focused hybrid/ticket tests under `tests/`

## Good Prompt

```text
Use GitHub to review Roi Snips. Read repo rogerclaw/roi-snips branch codex/hybrid-main-repo-sync and repo rogerclaw/roi-snips-architecture-packets. Start with CHATGPT_PRO_ROI_SNIPS_START_HERE.md, docs/CHATGPT_PRO_GITHUB_PLUGIN_START_HERE.md, docs/architecture/RESEARCH_TO_EXECUTION_TICKET_BOUNDARY.md, and source-packets/2026-05-31-hybrid-deep-mini-primary-restore/ROI_SNIPS_HYBRID_DEEP_MINI_PRIMARY_RESTORE_ACTION_PLAN_2026-05-31.md.

Audit whether code, config, scripts, and tests enforce the current architecture:
- Grok/X is heat/challenger only.
- OpenAI deep-mini/deep is the primary live selector.
- only a valid same-day Trade Authorization Ticket can authorize live/paper execution.
- deterministic final arming and order-router gates cannot be bypassed.

Return findings first, with file paths and exact reason. Then give a branch-sized patch plan, tests to add, validation commands, and rollback risks. Do not propose weakening risk gates or adding live-trading autonomy outside the ticket/guard boundary.
```

