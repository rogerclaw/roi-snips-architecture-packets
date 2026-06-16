#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _money(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(n) >= 1_000_000:
        return f"${n / 1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"${n / 1_000:.1f}K"
    return f"${n:.2f}"


def _pct(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _symbol(row: dict[str, Any] | None) -> str:
    if not row:
        return "none"
    return str(row.get("symbol") or row.get("ticker") or "unknown")


def _first_rows(rows: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows[:limit] if isinstance(row, dict)]


def _validation_stream(validation: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(validation, dict):
        return {}
    stream = validation.get("stream")
    return stream if isinstance(stream, dict) else {}


def _validation_passed(validation: dict[str, Any] | None) -> bool:
    if not isinstance(validation, dict):
        return False
    if validation.get("status") != "OK":
        return False
    if validation.get("all_steps_ok_or_shadow_allowed") is False:
        return False
    if validation.get("orders_allowed") is not False:
        return False
    if validation.get("orders_submitted") is not False:
        return False
    broker_flags = [
        validation.get("broker_account_inspected"),
        validation.get("broker_orders_inspected"),
        validation.get("broker_positions_inspected"),
    ]
    return all(flag is False for flag in broker_flags)


def compose_message(root: Path, trading_day: str) -> str:
    report = _load_json(root / "reports" / "morning" / "json" / f"{trading_day}.json")
    validation = _load_json(root / "reports" / "live_monitor" / f"next_open_shadow_validation_{trading_day}.json")

    if not isinstance(report, dict):
        return f"Roi Snips morning {trading_day}: morning report is missing, so I could not summarize picks. Check the scheduled runner artifacts."

    validation_ok = _validation_passed(validation if isinstance(validation, dict) else None)
    validation_status = validation.get("status") if isinstance(validation, dict) else "missing"
    validation_line = (
        f"No-order validation: PASS ({validation_status})."
        if validation_ok
        else f"No-order validation: NOT CLEAN ({validation_status}). Do not treat this as a ready trading readout."
    )

    if report.get("status") == "market_closed":
        session = report.get("market_session") if isinstance(report.get("market_session"), dict) else {}
        next_open = session.get("next_open") or "unknown"
        return "\n".join(
            [
                f"Roi Snips morning {trading_day}: market is closed for this run, so there is no pick.",
                validation_line,
                f"Next market open: {next_open}.",
                "",
                "Why no orders:",
                "- Market-closed report path.",
                f"- orders_allowed={validation.get('orders_allowed') if isinstance(validation, dict) else 'unknown'}, orders_submitted={validation.get('orders_submitted') if isinstance(validation, dict) else 'unknown'}.",
                f"- Broker account/orders/positions inspected: {validation.get('broker_account_inspected') if isinstance(validation, dict) else 'unknown'}/{validation.get('broker_orders_inspected') if isinstance(validation, dict) else 'unknown'}/{validation.get('broker_positions_inspected') if isinstance(validation, dict) else 'unknown'}.",
            ]
        )

    best = report.get("best_pick_candidate")
    best = best if isinstance(best, dict) else {}
    ranked = _first_rows(report.get("research_ranked"), 8)
    backups = report.get("ranked_backups")
    if not isinstance(backups, list):
        backups = []
    stream = _validation_stream(validation if isinstance(validation, dict) else None)

    raw_count = report.get("raw_candidate_count")
    enriched_count = report.get("enriched_candidate_count")
    source_status = report.get("source_lane_status")
    lanes = []
    if isinstance(source_status, list):
        lanes = [
            str(row.get("lane_name"))
            for row in source_status
            if isinstance(row, dict)
            and row.get("ran")
            and row.get("produced_useful_evidence_count", row.get("useful_evidence_count", row.get("useful_evidence", 0)))
        ]

    lines = [
        f"Roi Snips morning {trading_day}: research ran and picked {_symbol(best)} as primary.",
        validation_line,
        "Mode: no-order shadow only; this will not place paper or live trades.",
        "",
        "Research performed:",
        f"- Considered symbols: {', '.join(report.get('symbols_considered') or []) or 'none'}",
        f"- Raw candidates: {raw_count}; enriched packets: {enriched_count}",
        f"- Useful lanes: {', '.join(lanes[:8]) or 'none recorded'}",
        "",
        "Pick:",
        (
            f"- {_symbol(best)}: {best.get('catalyst_type', 'unknown catalyst')}; "
            f"{best.get('claim_summary', 'no claim summary')}; "
            f"last ${best.get('last_price', 'n/a')}; gap {_pct(best.get('gap_pct'))}; "
            f"premarket dollar volume {_money(best.get('premarket_dollar_volume'))}; "
            f"spread {_pct(best.get('spread_pct'))}; gate_pass={best.get('execution_gate_pass')}"
        ),
    ]

    if ranked:
        ranked_text = ", ".join(_symbol(row) for row in ranked[:5])
        lines.append(f"- Ranked list: {ranked_text}")
    if backups:
        lines.append("- Backups: " + ", ".join(f"{row.get('ticker', row.get('symbol', 'unknown'))}" for row in backups[:4] if isinstance(row, dict)))

    memo = _load_json(root / "runs" / trading_day / "normalized" / "daily_best_pick_packet.json")
    if isinstance(memo, dict):
        for key, label in [
            ("suggested_buy_zone", "Buy zone"),
            ("same_day_upside_target", "Same-day target"),
            ("one_to_three_day_upside_target", "1-3 day target"),
            ("thesis_break_level", "Thesis break"),
        ]:
            value = memo.get(key)
            if value:
                lines.append(f"- {label}: {value}")

    lines.extend(
        [
            "",
            "Why no orders:",
            f"- This scheduled run is still no-order shadow validation: orders_allowed={validation.get('orders_allowed') if isinstance(validation, dict) else 'unknown'}, orders_submitted={validation.get('orders_submitted') if isinstance(validation, dict) else 'unknown'}.",
            f"- Broker account/orders/positions inspected: {validation.get('broker_account_inspected') if isinstance(validation, dict) else 'unknown'}/{validation.get('broker_orders_inspected') if isinstance(validation, dict) else 'unknown'}/{validation.get('broker_positions_inspected') if isinstance(validation, dict) else 'unknown'}.",
            f"- Live stream generated proposals={stream.get('proposal_count', 'unknown')}, blocked_proposals={stream.get('blocked_proposal_count', 'unknown')}, fired_symbols={stream.get('fired_symbols', [])}.",
        ]
    )

    if report.get("deep_research_route") is None:
        lines.append("- Governed deep/mini research was not run; best-pick memo used internal fallback.")

    return "\n".join(lines)


def send_message(message: str, *, account: str, target: str, dry_run: bool) -> None:
    cmd = [
        "openclaw",
        "message",
        "send",
        "--channel",
        "telegram",
        "--account",
        account,
        "--target",
        target,
    ]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend(["--message", message])
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Send or print the Roi Snips morning update.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Trading day, YYYY-MM-DD.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--send", action="store_true", help="Send through OpenClaw Telegram instead of printing only.")
    parser.add_argument("--dry-run", action="store_true", help="Use OpenClaw dry-run when --send is set.")
    parser.add_argument("--account", default="roisnips")
    parser.add_argument("--target", default="8262254077")
    args = parser.parse_args()

    message = compose_message(args.root, args.date)
    if args.send:
        send_message(message, account=args.account, target=args.target, dry_run=args.dry_run)
    else:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
