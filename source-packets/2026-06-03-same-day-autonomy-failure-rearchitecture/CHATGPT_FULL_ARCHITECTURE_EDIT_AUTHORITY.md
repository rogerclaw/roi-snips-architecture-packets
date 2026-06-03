# ChatGPT Full Architecture and Config Edit Authority

Charles explicitly authorized ChatGPT to make full config-edit recommendations and to completely change Roi Snips architecture if needed.

This supersedes older review-packet language that asked ChatGPT only to audit or preserve the then-current ticket-boundary architecture.

## Authority Granted

ChatGPT may propose full changes to:

- `config/workflow.yaml`
- `configs/live.yaml`
- `configs/paper.yaml`
- schedule/timing model
- market-open orchestration
- deterministic discovery
- source-lane routing
- Grok/X role and optionality
- OpenAI deep-mini/deep research routing
- prompt generation
- Trade Authorization Ticket schema
- ticket validation
- stale-ticker quarantine
- stale-artifact hygiene
- final live arming gate
- opening monitor
- order-router constraints
- risk config
- Telegram/status update machinery
- runner/watchdog architecture
- GitHub/runtime checkout layout
- tests and validation matrix

ChatGPT may recommend deleting, replacing, or reorganizing existing modules if the current architecture is the wrong shape.

ChatGPT should not be limited to "make the current design work."

## Expected Output from ChatGPT

When reviewing this packet and the Roi Snips repo, ChatGPT should produce:

1. Findings first, with file paths and exact failure reasons.
2. A complete target architecture.
3. A branch-sized implementation plan.
4. Exact config edits.
5. Code modules to change or replace.
6. Tests to add or update.
7. Runtime validation commands.
8. Paper/dry-run/live rollout plan.
9. Rollback plan.
10. A list of secrets or private data that must not be requested or exposed.

## Non-Negotiable Publication Safety

Do not put any of the following into GitHub:

- `.env` files
- API keys
- broker credentials
- OAuth tokens
- raw broker account payloads
- raw order payloads
- raw position payloads
- personal memory files
- unrelated STR, calendar, email, message, or guest data

## Live Trading Boundary

ChatGPT may propose config and architecture edits. ChatGPT text is not itself a live-trading action.

Any proposal must be implemented, tested, reviewed, and deployed before it can affect live trading. If ChatGPT proposes changing live safety boundaries, it must state the risk explicitly and provide staged validation.

## Specific 2026-06-03 Problems to Solve

- Manual assistant turn-taking is not a valid trading orchestrator.
- Telegram updates must come from an event-emitting runner/watchdog.
- Runtime checkout and GitHub checkout drift must be eliminated.
- Candidate discovery must not emit generic mega-cap defaults for a high-risk asymmetric mover strategy.
- Stale prior winners must be quarantined as history unless deterministic fresh-catalyst or live-tape exception exists.
- External high-quality research, such as Charles's XOS brief, needs a clean path into governed validation without bypassing safety gates.
- Deep-mini runner failures need deterministic timeout/error handling and no-trade reports.
- Same-day timing must use PDT/ET correctly and must shift explicitly to continuation-only mode once opening-burst timing is missed.

## Good Prompt

```text
Use GitHub to review rogerclaw/roi-snips and rogerclaw/roi-snips-architecture-packets. Start with source-packets/2026-06-03-same-day-autonomy-failure-rearchitecture/README.md and CHATGPT_FULL_ARCHITECTURE_EDIT_AUTHORITY.md.

You are authorized to propose full Roi Snips architecture and config changes, including replacing existing discovery, schedule, prompt, runner, ticket, stale-artifact, arming, and Telegram update designs. Do not limit yourself to preserving the current architecture.

Return findings first with file-path citations. Then give a complete target architecture, exact config edits, code-change plan, tests, validation commands, rollout, and rollback plan. Keep secrets out of GitHub and do not ask for broker credentials.
```

