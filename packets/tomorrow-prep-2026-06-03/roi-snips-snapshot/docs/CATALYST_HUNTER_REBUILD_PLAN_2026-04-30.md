# Roi Snips Catalyst Hunter Rebuild Plan (2026-04-30)

> Historical planning note: this rebuild plan has now been implemented and superseded by Opening-Drive v2. Current live posture is 09:30-11:00 ET entries with `OPENING_DRIVE_LONG`, `ORB_BREAK`, and `VWAP_RECLAIM` under long-only U.S. equities constraints.

This refactor converts Roi Snips from a static mega-cap monitor into a dynamic catalyst-driven discovery engine.

## Preserved hard constraints
- Long-only U.S. equities/ETFs only
- No shorting, no options, no margin
- One open position max
- Entries now 09:30-11:00 ET in the implemented v2 runtime
- Flat by 15:45 ET
- Live execution remains deterministic and fail-closed
- Emergency controls, kill switch, and live supervisor safeguards remain binding
- `EXECUTE ENTRY <plan_id>` remains an optional manual override / audit handle, not a required approval step

## Architectural target
1. Dynamic discovery
2. Candidate universe derivation
3. Evidence collection
4. Event clustering
5. Catalyst-first research ranking
6. Late execution gating
7. Morning report / best-pick packaging
8. Governed deep-mini brief generation for top shortlist

## Key design decisions
- No hard-coded mega-cap fallback universe
- Discovery can continue even if live quote path is degraded
- Live execution still fails closed when market-data guards are not green
- Research ranking favors catalyst strength, freshness, attention acceleration, unusual volume, asymmetry, and still-early stories
- Execution filters are applied late, after research ranking
