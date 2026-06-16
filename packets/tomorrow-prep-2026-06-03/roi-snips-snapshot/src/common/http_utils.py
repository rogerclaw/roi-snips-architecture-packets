from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class HttpResponse:
    ok: bool
    status: int
    data: Any
    error: str | None = None


def _encode_params(params: dict[str, Any] | None) -> str:
    if not params:
        return ""
    return urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)


def http_get_json(url: str, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None, timeout: int = 20) -> HttpResponse:
    qs = _encode_params(params)
    full = f"{url}?{qs}" if qs else url
    req = urllib.request.Request(full, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body else None
            return HttpResponse(ok=True, status=resp.status, data=data)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return HttpResponse(ok=False, status=e.code, data=None, error=body or str(e))
    except Exception as e:
        return HttpResponse(ok=False, status=0, data=None, error=str(e))


def http_post_form_json(
    url: str,
    form: dict[str, Any],
    headers: dict[str, str] | None = None,
    basic_auth: tuple[str, str] | None = None,
    timeout: int = 20,
) -> HttpResponse:
    encoded = urllib.parse.urlencode(form).encode("utf-8")
    req_headers = {"Content-Type": "application/x-www-form-urlencoded", **(headers or {})}
    if basic_auth:
        raw = f"{basic_auth[0]}:{basic_auth[1]}".encode("utf-8")
        req_headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    req = urllib.request.Request(url, data=encoded, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body else None
            return HttpResponse(ok=True, status=resp.status, data=data)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return HttpResponse(ok=False, status=e.code, data=None, error=body or str(e))
    except Exception as e:
        return HttpResponse(ok=False, status=0, data=None, error=str(e))


def http_post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 20,
) -> HttpResponse:
    qs = _encode_params(params)
    full = f"{url}?{qs}" if qs else url
    body = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", "Accept": "application/json", **(headers or {})}
    req = urllib.request.Request(full, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            data = json.loads(text) if text else None
            return HttpResponse(ok=True, status=resp.status, data=data)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return HttpResponse(ok=False, status=e.code, data=None, error=body_text or str(e))
    except Exception as e:
        return HttpResponse(ok=False, status=0, data=None, error=str(e))
