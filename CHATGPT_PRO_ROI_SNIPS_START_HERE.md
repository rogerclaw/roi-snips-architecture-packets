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

## 2026-06-03 Full Rearchitecture Authority

Charles has now explicitly authorized ChatGPT to propose full Roi Snips config edits and complete architecture changes. This supersedes older packet language that only asked ChatGPT to preserve the current architecture.

Start with:

- `source-packets/2026-06-03-same-day-autonomy-failure-rearchitecture/README.md`
- `source-packets/2026-06-03-same-day-autonomy-failure-rearchitecture/CHATGPT_FULL_ARCHITECTURE_EDIT_AUTHORITY.md`
- `source-packets/2026-06-03-same-day-autonomy-failure-rearchitecture/TELEGRAM_TIMELINE_SANITIZED.md`

ChatGPT may recommend replacing discovery, schedule, prompt generation, model routing, ticket schema, stale-artifact hygiene, final arming, live monitor, risk config, Telegram update machinery, and runtime/GitHub checkout layout if the current design is wrong.

The boundary is publication and runtime safety: do not expose secrets, `.env`, broker credentials, raw broker account/order/position payloads, or unrelated private workspace data. ChatGPT's text is a proposal until implemented, tested, committed, and deployed.

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
Use GitHub to review Roi Snips. Read repo rogerclaw/roi-snips and repo rogerclaw/roi-snips-architecture-packets. Start with CHATGPT_PRO_ROI_SNIPS_START_HERE.md, source-packets/2026-06-03-same-day-autonomy-failure-rearchitecture/README.md, and source-packets/2026-06-03-same-day-autonomy-failure-rearchitecture/CHATGPT_FULL_ARCHITECTURE_EDIT_AUTHORITY.md.

Charles authorizes you to propose full config and architecture changes, including replacing the current discovery, schedule, prompt, runner, ticket, stale-artifact, final arming, monitor, and Telegram update design if needed.

Return findings first, with file paths and exact reasons. Then give a complete target architecture, exact config edits, branch-sized patch plan, tests to add, validation commands, rollout plan, and rollback risks. Keep secrets and broker credentials out of GitHub.
```
