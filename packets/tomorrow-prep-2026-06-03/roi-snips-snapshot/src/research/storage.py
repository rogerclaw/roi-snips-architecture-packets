from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from ..common.config import repo_root


SUBDIRS = ["meta", "raw", "normalized", "overlays", "verification", "output", "logs"]


class ResearchRunStorage:
    def __init__(self, trading_day: str | None = None, root: Path | None = None) -> None:
        self.trading_day = trading_day or os.getenv("ROI_SNIPS_TRADE_DATE", "").strip() or datetime.now().strftime("%Y-%m-%d")
        self.root = root or (repo_root() / "runs" / self.trading_day)
        for subdir in SUBDIRS:
            (self.root / subdir).mkdir(parents=True, exist_ok=True)

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def write_json(self, relative_path: str, payload: Any) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return path

    def write_jsonl(self, relative_path: str, rows: Iterable[dict[str, Any]], append: bool = False) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with path.open(mode) as f:
            for row in rows:
                f.write(json.dumps(row, sort_keys=True) + "\n")
        return path

    def read_json(self, relative_path: str) -> Any:
        return json.loads((self.root / relative_path).read_text())

    def read_jsonl(self, relative_path: str) -> list[dict[str, Any]]:
        path = self.root / relative_path
        if not path.exists():
            return []
        rows = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows
