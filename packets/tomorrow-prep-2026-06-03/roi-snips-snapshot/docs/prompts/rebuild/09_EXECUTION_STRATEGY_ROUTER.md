# 09 Execution Strategy Router

Route the best candidate to a deterministic strategy: `OPENING_BURST_HYPER_LONG`, `GAP_AND_GO_CONFIRMATION`, `PREMARKET_HIGH_RECLAIM`, `VWAP_WASHOUT_RECLAIM`, `ORB_BREAK_1MIN`, `ORB_BREAK_5MIN`, `SECOND_LEG_CONTINUATION`, `EVENT_TIMED_HEADLINE_REACTION`, `EVENT_PREPOSITION_STARTER`, `NEWS_RELEASE_SCALP`, `HALT_REOPEN_REACTION`, or `NO_TRADE_WAIT`.

The LLM may recommend a route but must not place, preview, replace, or cancel orders.
