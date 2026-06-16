from src.approval.approval_gate import parse_operator_command


def test_execute_entry_parse():
    decision = parse_operator_command("EXECUTE ENTRY plan_123")
    assert decision.action == "EXECUTE_ENTRY"
    assert decision.plan_id == "plan_123"


def test_legacy_approve_entry_parse_aliases_to_execute():
    decision = parse_operator_command("APPROVE ENTRY plan_123")
    assert decision.action == "EXECUTE_ENTRY"
    assert decision.plan_id == "plan_123"


def test_disable_new_entries_parse():
    decision = parse_operator_command("DISABLE NEW ENTRIES")
    assert decision.action == "DISABLE_NEW_ENTRIES"
