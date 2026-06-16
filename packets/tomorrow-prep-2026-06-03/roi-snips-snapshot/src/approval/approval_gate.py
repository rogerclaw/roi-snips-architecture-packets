"""Telegram/operator command parser for v1."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ApprovalDecision:
    action: str
    plan_id: str | None = None
    reason: str | None = None
    alert_id: str | None = None


def parse_operator_command(text: str) -> ApprovalDecision:
    raw = text.strip()
    upper = raw.upper()

    if upper.startswith("EXECUTE ENTRY "):
        return ApprovalDecision(action="EXECUTE_ENTRY", plan_id=raw.split(maxsplit=2)[2])

    if upper.startswith("APPROVE ENTRY "):
        return ApprovalDecision(action="EXECUTE_ENTRY", plan_id=raw.split(maxsplit=2)[2])

    if upper.startswith("REJECT ENTRY "):
        parts = raw.split(maxsplit=3)
        plan_id = parts[2] if len(parts) > 2 else None
        reason = parts[3] if len(parts) > 3 else None
        return ApprovalDecision(action="REJECT_ENTRY", plan_id=plan_id, reason=reason)

    if upper == "DISABLE NEW ENTRIES":
        return ApprovalDecision(action="DISABLE_NEW_ENTRIES")

    if upper == "ENABLE NEW ENTRIES":
        return ApprovalDecision(action="ENABLE_NEW_ENTRIES")

    if upper == "FLAT ALL NOW":
        return ApprovalDecision(action="FLAT_ALL_NOW")

    if upper.startswith("ACK ALERT "):
        parts = raw.split(maxsplit=2)
        alert_id = parts[2] if len(parts) > 2 else None
        return ApprovalDecision(action="ACK_ALERT", alert_id=alert_id)

    if upper == "STATUS":
        return ApprovalDecision(action="STATUS")

    return ApprovalDecision(action="UNKNOWN")


def approval_matches_plan(command_text: str, plan_id: str) -> bool:
    decision = parse_operator_command(command_text)
    return decision.action == "EXECUTE_ENTRY" and decision.plan_id == plan_id
