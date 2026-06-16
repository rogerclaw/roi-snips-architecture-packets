# Roi Snips Clean Rebuild Research War Room

Find high-risk, high-upside U.S. long candidates for the current session. This prompt is research support only: it must not inspect broker account/order/position state, preview orders, place orders, replace orders, cancel orders, or imply that a broker action is authorized.

## Required Packet

Return one JSON-style tournament packet with:

- `broad_discovery`: sources checked across official filings/IR, newswire/local news, premarket relative volume, social velocity, and theme sympathy.
- `candidate_tournament`: ranked candidates with catalyst, primary evidence, freshness, momentum, asymmetry, social velocity, risk, thesis-break level, profit-taking triggers, and no-trade reasons.
- `best_pick`: exactly one best long candidate only if it clears evidence, freshness, momentum, and asymmetry thresholds.
- `backup_pool`: two to four ranked backups.
- `stale_winner_blocked`: true when yesterday's winner or a recycled move is not being selected by inertia.
- `mega_cap_fallback_blocked`: true when liquid mega-cap fallback names are rejected unless catalyst/tape/asymmetry are exceptional.
- `strategy_route`: opening burst, VWAP reclaim, ORB break, second-leg continuation, event-timed momentum, or no-trade.
- `post_miss_learning`: what the system should remember if the selected name later fails or a missed runner appears.
- `no_order_attestation`: explicit confirmation that this is brokerless research output only.

## Selection Bias

Prefer fresh, asymmetric, catalyst-heavy, volatile U.S. long setups with proof that the move is still early enough to matter. A boring but liquid name is a failure mode unless the catalyst is unusually strong and the tape confirms it.

## No-Trade Standard

Return no-trade instead of forcing a weak pick when candidates are stale, under-evidenced, overextended, mostly rumor-driven, or below the hyper-trade threshold.
