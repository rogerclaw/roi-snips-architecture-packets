from __future__ import annotations

from typing import Any

from ..raw_discovery import build_raw_runner_candidates


class RawRunnerScout:
    """Adapter wrapper that turns already-collected events into raw runner rows."""

    def collect_from_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return build_raw_runner_candidates(events, preserve_top_n=150)
