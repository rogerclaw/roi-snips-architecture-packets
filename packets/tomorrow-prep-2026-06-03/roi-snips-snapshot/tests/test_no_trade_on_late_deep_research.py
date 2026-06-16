from tests.test_trade_authorization_ticket import valid_ticket
from src.research.trade_authorization_ticket import validate_ticket


def test_late_deep_research_ticket_invalid_for_opening_bell():
    result = validate_ticket({**valid_ticket("INFQ"), "completed_before_deadline": False})
    assert result.valid is False
    assert "deep_research_ticket_invalid_or_late" in result.blockers
