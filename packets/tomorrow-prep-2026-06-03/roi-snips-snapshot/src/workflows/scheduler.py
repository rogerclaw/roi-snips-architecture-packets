from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from ..approval.command_processor import CommandProcessor
from ..common.config import load_live_config, load_workflow_config
from ..common.telegram import TelegramNotifier
from .live_monitor import run_live_monitor_once
from .premarket_pipeline import build_premarket_report, write_report
from .research_pipeline import ResearchPipeline


class RoiSnipsScheduler:
    def __init__(self) -> None:
        self.live_cfg = load_live_config()
        self.workflow_cfg = load_workflow_config()
        self.scheduler = BlockingScheduler(timezone=(self.live_cfg.get("session") or {}).get("timezone", "America/New_York"))
        self.notifier = TelegramNotifier()
        self.command_processor = CommandProcessor(self.live_cfg)

    def _report_summary_text(self, report: dict[str, Any]) -> str:
        a_tier = (report.get("watchlist") or {}).get("A") or []
        symbols = ", ".join(row.get("symbol", "?") for row in a_tier[:3]) or "none"
        return f"Roi Snips morning report\nstatus: {report.get('status')}\nA-tier: {symbols}"

    def run_premarket_job(self) -> dict[str, Any]:
        report = build_premarket_report()
        root = Path(__file__).resolve().parents[2]
        json_path, md_path = write_report(report, root)
        result = {"ok": True, "status": report.get("status"), "json": str(json_path), "md": str(md_path)}
        if self.notifier.configured():
            self.notifier.send(self._report_summary_text(report))
        return result

    def run_live_monitor_job(self) -> dict[str, Any]:
        return run_live_monitor_once()

    def run_research_job(self) -> dict[str, Any]:
        result = ResearchPipeline().run_once()
        if self.notifier.configured():
            self.notifier.send(
                "Roi Snips research pass\n"
                f"mode={result.get('mode')}\n"
                f"status={result.get('status')}\n"
                f"authorized_ticker={((result.get('summary') or {}).get('best_pick') or 'none')}"
            )
        return result

    def run_force_flat_job(self) -> dict[str, Any]:
        result = self.command_processor.process("FLAT ALL NOW", source="scheduler")
        if self.notifier.configured():
            self.notifier.send(f"Roi Snips force-flat result\n{json.dumps(result)}")
        return result

    def install_jobs(self) -> None:
        workflow = self.workflow_cfg.get("workflow") or {}
        premarket_times = workflow.get("premarket_schedule_et") or []
        for idx, hhmm in enumerate(premarket_times):
            hour, minute = [int(part) for part in str(hhmm).split(":", 1)]
            self.scheduler.add_job(
                self.run_premarket_job,
                CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute),
                id=f"premarket_{idx}_{hour:02d}{minute:02d}",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )

        research_passes = workflow.get("research_passes_et") or {}
        for name, schedule in research_passes.items():
            start = str((schedule or {}).get("start") or "").strip()
            if not start:
                continue
            hour, minute = [int(part) for part in start.split(":", 1)]
            self.scheduler.add_job(
                self.run_research_job,
                CronTrigger(day_of_week="mon-fri", hour=hour, minute=minute),
                id=f"research_{name}",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )

        poll_seconds = int((workflow.get("live_engine") or {}).get("poll_seconds", 30))
        self.scheduler.add_job(
            self.run_live_monitor_job,
            "interval",
            seconds=poll_seconds,
            id="live_monitor",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

        session = self.live_cfg.get("session") or {}
        force_flat = str(session.get("force_flat_all_et", "15:45"))
        flat_hour, flat_minute = [int(part) for part in force_flat.split(":", 1)]
        self.scheduler.add_job(
            self.run_force_flat_job,
            CronTrigger(day_of_week="mon-fri", hour=flat_hour, minute=flat_minute),
            id="force_flat",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

    def run(self) -> None:
        self.install_jobs()
        self.scheduler.start()


if __name__ == "__main__":
    RoiSnipsScheduler().run()
