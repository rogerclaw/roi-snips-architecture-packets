from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..common.config import load_env_file
from ..common.http_utils import HttpResponse


def _default_base_url(environment: str, region_id: str) -> str:
    env = (environment or "prod").strip().lower()
    region = (region_id or "us").strip().lower()
    if env in {"uat", "test", "paper", "sandbox"}:
        return f"https://{region}-openapi-alb.uat.webullbroker.com"
    return "https://api.webull.com"


@dataclass
class WebullRESTConfig:
    app_key: str
    app_secret: str
    region_id: str = "us"
    environment: str = "prod"
    base_url: str = ""
    access_token: str = ""

    @classmethod
    def from_env(cls) -> "WebullRESTConfig":
        load_env_file()
        environment = os.getenv("WEBULL_ENVIRONMENT", "prod")
        region_id = os.getenv("WEBULL_REGION_ID", "us")
        base_url = os.getenv("WEBULL_HTTP_API_BASE", "").strip()
        if not base_url:
            base_url = _default_base_url(environment, region_id)
        return cls(
            app_key=os.getenv("WEBULL_APP_KEY", ""),
            app_secret=os.getenv("WEBULL_APP_SECRET", ""),
            region_id=region_id,
            environment=environment,
            base_url=base_url,
            access_token=os.getenv("WEBULL_ACCESS_TOKEN", ""),
        )


class WebullRESTClient:
    def __init__(self, cfg: WebullRESTConfig | None = None) -> None:
        self.cfg = cfg or WebullRESTConfig.from_env()

    def has_creds(self) -> bool:
        return bool(self.cfg.app_key and self.cfg.app_secret and self.cfg.base_url)

    def _host(self) -> str:
        return urllib.parse.urlparse(self.cfg.base_url).netloc

    @staticmethod
    def _json_body(body: dict[str, Any] | None) -> str | None:
        if body is None:
            return None
        return json.dumps(body, separators=(",", ":"), ensure_ascii=False)

    def _signed_headers(
        self,
        path: str,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
        nonce: str | None = None,
    ) -> dict[str, str]:
        ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        nonce = nonce or uuid.uuid4().hex
        sign_params = {
            "host": self._host(),
            "x-app-key": self.cfg.app_key,
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-version": "1.0",
            "x-signature-nonce": nonce,
            "x-timestamp": ts,
        }
        for key, value in (query or {}).items():
            if value is None:
                continue
            text = "&".join(sorted(str(v) for v in value)) if isinstance(value, (list, tuple)) else str(value)
            current = sign_params.get(key)
            sign_params[key] = f"{current}&{text}" if current is not None else text

        body_text = self._json_body(body)
        string_to_sign = path + "&" + "&".join(f"{k}={v}" for k, v in sorted(sign_params.items(), key=lambda item: item[0]))
        if body_text is not None:
            string_to_sign += "&" + hashlib.md5(body_text.encode("utf-8")).hexdigest().upper()
        encoded = urllib.parse.quote(string_to_sign, safe="")
        signature = base64.b64encode(
            hmac.new((self.cfg.app_secret + "&").encode("utf-8"), encoded.encode("utf-8"), hashlib.sha1).digest()
        ).decode("ascii")

        headers = {
            "Accept": "application/json",
            "x-app-key": self.cfg.app_key,
            "x-timestamp": ts,
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-version": "1.0",
            "x-signature-nonce": nonce,
            "x-version": "v2",
            "x-signature": signature,
        }
        if body_text is not None:
            headers["Content-Type"] = "application/json"
        return headers

    def request_json(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        access_token: str | None = None,
        timeout: int = 20,
    ) -> HttpResponse:
        if not self.has_creds():
            return HttpResponse(ok=False, status=0, data=None, error="missing_webull_credentials")

        headers = self._signed_headers(path, query=query, body=body)
        token = access_token if access_token is not None else self.cfg.access_token
        if token:
            headers["x-access-token"] = token

        url = urllib.parse.urljoin(self.cfg.base_url.rstrip("/") + "/", path.lstrip("/"))
        qs = urllib.parse.urlencode({k: v for k, v in (query or {}).items() if v is not None}, doseq=True)
        if qs:
            url = f"{url}?{qs}"

        body_text = self._json_body(body)
        data = body_text.encode("utf-8") if body_text is not None else None
        req = urllib.request.Request(url, headers=headers, data=data, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(raw) if raw else None
                except Exception:
                    parsed = raw
                return HttpResponse(ok=True, status=resp.status, data=parsed)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
            return HttpResponse(ok=False, status=e.code, data=None, error=raw or str(e))
        except Exception as e:
            return HttpResponse(ok=False, status=0, data=None, error=str(e))

    def create_token(self) -> HttpResponse:
        return self.request_json("POST", "/openapi/auth/token/create")

    def check_token(self, token: str | None = None) -> HttpResponse:
        use_token = token or self.cfg.access_token
        if not use_token:
            return HttpResponse(ok=False, status=0, data=None, error="missing_webull_access_token")
        return self.request_json("POST", "/openapi/auth/token/check", body={"token": use_token})

    def list_accounts(self, token: str | None = None) -> HttpResponse:
        use_token = token or self.cfg.access_token
        if not use_token:
            return HttpResponse(ok=False, status=0, data=None, error="missing_webull_access_token")
        return self.request_json("GET", "/openapi/account/list", access_token=use_token)

    def stock_snapshot(
        self,
        symbols: str | list[str],
        *,
        category: str = "US_STOCK",
        extend_hour_required: bool = True,
        overnight_required: bool = False,
        token: str | None = None,
    ) -> HttpResponse:
        symbol_text = symbols if isinstance(symbols, str) else ",".join(symbols)
        return self.request_json(
            "GET",
            "/openapi/market-data/stock/snapshot",
            query={
                "symbols": symbol_text,
                "category": category,
                "extend_hour_required": str(bool(extend_hour_required)).lower(),
                "overnight_required": str(bool(overnight_required)).lower(),
            },
            access_token=token,
        )

    def stock_bars(
        self,
        symbol: str,
        *,
        category: str = "US_STOCK",
        timespan: str = "M1",
        count: int = 60,
        real_time_required: bool = True,
        trading_sessions: list[str] | None = None,
        token: str | None = None,
    ) -> HttpResponse:
        query: dict[str, Any] = {
            "symbol": symbol,
            "category": category,
            "timespan": timespan,
            "count": count,
        }
        if real_time_required:
            query["real_time_required"] = str(bool(real_time_required)).lower()
        if trading_sessions:
            query["trading_sessions"] = ",".join(trading_sessions)
        return self.request_json(
            "GET",
            "/openapi/market-data/stock/bars",
            query=query,
            access_token=token,
        )

    def account_balance(self, account_id: str) -> HttpResponse:
        return self.request_json("GET", "/openapi/assets/balance", query={"account_id": account_id})

    def account_positions(self, account_id: str) -> HttpResponse:
        return self.request_json("GET", "/openapi/assets/positions", query={"account_id": account_id})

    def open_orders(self, account_id: str, *, page_index: int = 1, page_size: int = 50) -> HttpResponse:
        bounded_page_size = max(10, min(int(page_size), 100))
        return self.request_json(
            "GET",
            "/openapi/trade/order/open",
            query={"account_id": account_id, "page_index": page_index, "page_size": bounded_page_size},
        )

    def order_history(self, account_id: str, *, page_index: int = 1, page_size: int = 50) -> HttpResponse:
        bounded_page_size = max(10, min(int(page_size), 100))
        return self.request_json(
            "GET",
            "/openapi/trade/order/history",
            query={"account_id": account_id, "page_index": page_index, "page_size": bounded_page_size},
        )

    def order_detail(self, account_id: str, client_order_id: str) -> HttpResponse:
        return self.request_json(
            "GET",
            "/openapi/trade/order/detail",
            query={"account_id": account_id, "client_order_id": client_order_id},
        )
