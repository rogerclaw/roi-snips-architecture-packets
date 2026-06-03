"""Grok-backed web/X search adapter.

This adapter intentionally treats Grok output as discovery evidence only. It
uses the local OpenClaw web-search capability so credentials stay in the
governed OpenClaw auth path rather than Roi Snips env files.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from typing import Any


TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b")
DEFAULT_BROAD_QUERIES = [
    'site:x.com "$" stock catalyst unusual volume premarket today',
    'site:x.com "$" stock FDA contract earnings guidance squeeze today',
]


class GrokSearchAdapter:
    def __init__(
        self,
        *,
        provider: str | None = None,
        openclaw_bin: str | None = None,
        timeout_seconds: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.provider = provider or os.getenv("ROI_SNIPS_GROK_SEARCH_PROVIDER", "grok")
        self.openclaw_bin = openclaw_bin or os.getenv("OPENCLAW_BIN", "openclaw")
        self.timeout_seconds = int(timeout_seconds or os.getenv("ROI_SNIPS_GROK_SEARCH_TIMEOUT_SECONDS", "45"))
        if enabled is None:
            enabled = os.getenv("ROI_SNIPS_ENABLE_GROK_X_SCOUT", "true").strip().lower() in {"1", "true", "yes", "on"}
        self.enabled = bool(enabled)

    def search(self, query: str, *, limit: int = 5) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "reason": "grok_x_scout_disabled", "optional": True}
        command = [
            self.openclaw_bin,
            "infer",
            "web",
            "search",
            "--provider",
            self.provider,
            "--query",
            query,
            "--limit",
            str(limit),
            "--json",
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "grok_search_timeout", "optional": True}
        except Exception as exc:
            return {"ok": False, "reason": "grok_search_error", "error": str(exc), "optional": True}

        if completed.returncode != 0:
            return {
                "ok": False,
                "reason": "grok_search_nonzero_exit",
                "exit_code": completed.returncode,
                "stderr": completed.stderr.strip(),
                "stdout": completed.stdout.strip(),
                "optional": True,
            }

        try:
            payload = json.loads(completed.stdout)
        except Exception as exc:
            return {"ok": False, "reason": "grok_search_bad_json", "error": str(exc), "stdout": completed.stdout.strip(), "optional": True}

        result = (((payload.get("outputs") or [{}])[0] or {}).get("result") or {}) if isinstance(payload, dict) else {}
        return {
            "ok": bool(payload.get("ok", True)),
            "provider": result.get("provider") or self.provider,
            "model": result.get("model"),
            "query": result.get("query") or query,
            "content": result.get("content") or "",
            "citations": result.get("citations") or [],
            "raw": payload,
        }

    def fetch_x_candidates(
        self,
        tickers: list[str] | None = None,
        *,
        broad_queries: list[str] | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        symbols = [str(t).strip().upper() for t in (tickers or []) if str(t).strip()]
        if symbols:
            query = "site:x.com (" + " OR ".join(f"${ticker}" for ticker in symbols[:12]) + ") stock catalyst momentum today"
            queries = [query]
        else:
            queries = broad_queries or DEFAULT_BROAD_QUERIES

        searches: list[dict[str, Any]] = []
        counts: Counter[str] = Counter()
        urls_by_ticker: dict[str, set[str]] = defaultdict(set)
        snippets_by_ticker: dict[str, list[str]] = defaultdict(list)
        failures: list[dict[str, Any]] = []

        for query in queries:
            res = self.search(query, limit=limit)
            searches.append({k: v for k, v in res.items() if k != "raw"})
            if not res.get("ok"):
                failures.append(res)
                continue
            content = str(res.get("content") or "")
            citations = [str(url) for url in (res.get("citations") or []) if str(url).strip()]
            symbols_found = TICKER_RE.findall(content)
            for symbol in symbols_found:
                counts[symbol] += 1
                snippets_by_ticker[symbol].append(content[:1000])
                for url in citations:
                    if "x.com" in url or "twitter.com" in url:
                        urls_by_ticker[symbol].add(url)

        candidates = [
            {
                "ticker": ticker,
                "mentions": count,
                "evidence_urls": sorted(urls_by_ticker.get(ticker) or []),
                "snippets": snippets_by_ticker.get(ticker, [])[:2],
            }
            for ticker, count in counts.most_common()
        ]
        return {
            "ok": bool(candidates) or (bool(searches) and not failures),
            "provider": self.provider,
            "auth_mode": "openclaw_grok_web_search",
            "searches": searches,
            "failures": failures,
            "candidates": candidates,
        }
