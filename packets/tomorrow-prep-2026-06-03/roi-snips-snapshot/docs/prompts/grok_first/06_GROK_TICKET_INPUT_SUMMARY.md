Summarize Grok/X heat, web verification, social velocity, and challenger notes for the governed deep-mini prompt.

Rules:

- Grok cannot create a live-valid Trade Authorization Ticket.
- Grok cannot select the live stock by itself.
- Grok cannot authorize backups or override deep-mini.
- Any Grok-favored name is research-only until deep-mini/governed deep research authorizes it.

Return strict JSON:

```json
{
  "stage": "grok_ticket_input_summary",
  "status": "completed|failed",
  "candidate_recommendations": [],
  "names_for_deep_mini_to_judge": [],
  "verified_social_catalysts": [],
  "rumor_only_names": [],
  "pump_risk_names": [],
  "grok_research_only": true,
  "can_authorize_live_trade": false,
  "live_authorization_rule": "Deep-mini/governed deep research must create the only live-valid ticket."
}
```
