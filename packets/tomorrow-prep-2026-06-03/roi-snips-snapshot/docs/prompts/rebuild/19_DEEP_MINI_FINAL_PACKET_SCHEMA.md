The deep-mini final packet must include:

1. single best stock or no-trade
2. ticker/company
3. exact catalyst
4. why it can move today or within 1-3 days
5. why market may not have fully priced it
6. official/structured/social/market evidence
7. sentiment trend
8. premarket / early-session behavior
9. limit buy range or wait trigger
10. same-day target
11. 1-3 day target
12. downside / thesis break
13. monitoring windows
14. profit-taking triggers
15. danger signals
16. chosen strategy
17. same-style backups
18. no-trade rejects
19. source breadth status
20. deep-mini run IDs / request IDs / output paths
21. red-team verdict
22. live execution readiness gate status

If deep-mini did not run, timed out, failed, or returned unparsed output, final packet status must be `NO_TRADE_RESEARCH_INCOMPLETE` for live trading and `executable_primary` must be null. Do not output a deterministic fallback as executable for live.
