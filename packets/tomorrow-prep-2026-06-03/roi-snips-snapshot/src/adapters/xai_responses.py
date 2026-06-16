"""xAI/Grok search and structured-output adapter.

The adapter exposes research-only capabilities. It intentionally has no broker,
order, account, position, preview, cancel, or replace methods.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass
class XAIResponsesAdapter:
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    openclaw_bin: str | None = None
    timeout_seconds: int | None = None
    client: Any | None = None

    def __post_init__(self) -> None:
        self.model = self.model or os.getenv("ROI_SNIPS_GROK_MODEL", "grok-4.3")
        self.api_key = self.api_key or os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
        self.base_url = (self.base_url or os.getenv("XAI_BASE_URL") or "https://api.x.ai/v1").rstrip("/")
        self.openclaw_bin = self.openclaw_bin or os.getenv("OPENCLAW_BIN", "openclaw")
        self.timeout_seconds = int(self.timeout_seconds or os.getenv("ROI_SNIPS_GROK_SEARCH_TIMEOUT_SECONDS", "45"))

    @property
    def has_api_key(self) -> bool:
        return bool(str(self.api_key or "").strip())

    def search(self, query: str, *, tool: str = "web_search", limit: int = 8) -> dict[str, Any]:
        if self.client is not None:
            return self.client.search(query=query, tool=tool, limit=limit)
        if os.getenv("ROI_SNIPS_GROK_USE_OPENCLAW_SEARCH", "true").strip().lower() in {"1", "true", "yes", "on"}:
            return self._openclaw_search(query, tool=tool, limit=limit)
        return self._xai_chat_search(query, tool=tool)

    def structured_completion(self, prompt: str, *, schema_name: str = "grok_research_json") -> dict[str, Any]:
        if self.client is not None:
            return self.client.structured_completion(prompt=prompt, schema_name=schema_name)
        if not self.has_api_key:
            return {"ok": False, "reason": "xai_api_key_missing", "model": self.model}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Return strict JSON only. No prose outside JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        return self._post_chat_completions(payload, parse_json=True)

    def _openclaw_search(self, query: str, *, tool: str, limit: int) -> dict[str, Any]:
        routed_query = query
        if tool == "x_search" and "site:x.com" not in query and "site:twitter.com" not in query:
            routed_query = f"site:x.com {query}"
        command = [
            str(self.openclaw_bin),
            "infer",
            "web",
            "search",
            "--provider",
            "grok",
            "--query",
            routed_query,
            "--limit",
            str(limit),
            "--json",
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "grok_search_timeout", "tool": tool, "query": query}
        except Exception as exc:
            return {"ok": False, "reason": "grok_search_error", "error": str(exc), "tool": tool, "query": query}
        if completed.returncode != 0:
            return {
                "ok": False,
                "reason": "grok_search_nonzero_exit",
                "exit_code": completed.returncode,
                "stderr": completed.stderr.strip(),
                "stdout": completed.stdout.strip(),
                "tool": tool,
                "query": query,
            }
        try:
            payload = json.loads(completed.stdout)
        except Exception as exc:
            return {"ok": False, "reason": "grok_search_bad_json", "error": str(exc), "stdout": completed.stdout.strip(), "tool": tool, "query": query}
        result = (((payload.get("outputs") or [{}])[0] or {}).get("result") or {}) if isinstance(payload, dict) else {}
        return {
            "ok": bool(payload.get("ok", True)),
            "tool": tool,
            "provider": result.get("provider") or "grok",
            "model": result.get("model") or self.model,
            "query": result.get("query") or routed_query,
            "content": result.get("content") or "",
            "citations": result.get("citations") or [],
            "raw": payload,
        }

    def _xai_chat_search(self, query: str, *, tool: str) -> dict[str, Any]:
        if not self.has_api_key:
            return {"ok": False, "reason": "xai_api_key_missing", "tool": tool, "query": query, "model": self.model}
        prompt = f"Use current {'X/cashtag' if tool == 'x_search' else 'web'} search evidence for this query and cite sources:\n{query}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        return self._post_chat_completions(payload, parse_json=False) | {"tool": tool, "query": query}

    def _post_chat_completions(self, payload: dict[str, Any], *, parse_json: bool) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return {"ok": False, "reason": "xai_http_error", "status": exc.code, "body": exc.read().decode("utf-8", "replace")[:2000]}
        except Exception as exc:
            return {"ok": False, "reason": "xai_request_error", "error": str(exc)}
        try:
            payload_out = json.loads(raw)
        except Exception as exc:
            return {"ok": False, "reason": "xai_response_bad_json", "error": str(exc), "raw": raw[:2000]}
        content = (((payload_out.get("choices") or [{}])[0] or {}).get("message") or {}).get("content") or ""
        out: dict[str, Any] = {"ok": True, "model": payload_out.get("model") or self.model, "content": content, "raw": payload_out}
        if parse_json:
            parsed = parse_json_object(content)
            out["parsed_json"] = parsed
            if parsed is None:
                out["ok"] = False
                out["reason"] = "structured_output_unparsed"
        return out


def parse_json_object(text: str) -> dict[str, Any] | None:
    text = str(text or "").strip()
    if not text:
        return None
    for candidate in [text, *(match.group(1) for match in JSON_BLOCK_RE.finditer(text))]:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None
