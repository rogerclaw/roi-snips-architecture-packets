from __future__ import annotations

import os
from typing import Any

from .config import load_env_file
from .http_utils import http_post_form_json


class TelegramNotifier:
    def __init__(self) -> None:
        load_env_file()
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""

    def configured(self) -> bool:
        return bool(self.base_url and self.chat_id)

    def send(self, text: str, chat_id: str | None = None) -> dict[str, Any]:
        if not self.configured() and not (self.base_url and chat_id):
            return {"ok": False, "reason": "telegram_not_configured"}
        target = chat_id or self.chat_id
        res = http_post_form_json(f"{self.base_url}/sendMessage", {"chat_id": target, "text": text})
        return {"ok": res.ok, "status": res.status, "data": res.data, "error": res.error}
