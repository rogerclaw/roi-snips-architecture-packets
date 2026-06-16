from src.workflows.premarket_pipeline import _same_style_backup_status
from tests.runbook_helpers import ranked_row


def test_same_style_backups_prefer_non_megacap_catalyst_names() -> None:
    rows = [
        ranked_row("INFQ"),
        ranked_row("QTUM", hyper=8.0),
        ranked_row("BWIN", hyper=7.5),
        ranked_row("ATOM", hyper=7.2),
        ranked_row("AAPL", hyper=9.0, lanes=["VERIFIED_CATALYST_RUNNER"]),
    ]

    status = _same_style_backup_status(rows, "INFQ")

    assert status["same_style_backup_pool_ok"] is True
    assert status["same_style_non_megacap_backups"][:3] == ["QTUM", "BWIN", "ATOM"]
    assert "AAPL" not in status["same_style_non_megacap_backups"]
