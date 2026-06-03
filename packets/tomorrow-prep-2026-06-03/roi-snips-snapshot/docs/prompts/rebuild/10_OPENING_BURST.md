# 10 Opening Burst

Use SIP quotes/trades for opening tape. Respect the state machine: `PREOPEN_FREEZE`, `FIRST_PRINT_OBSERVE`, `FIRST_10S`, `FIRST_30S`, `FIRST_60S`, rescue/reclaim, then continuation.

No blind market orders. Opening entries require aggressive limits, exit manager readiness, quote freshness, spread guard, halt guard, and brokerless/live-mode authorization gates.
