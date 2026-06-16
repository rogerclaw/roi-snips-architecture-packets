from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ..common.config import controls_paths, load_env_file, load_live_config
from ..common.http_utils import http_get_json, http_post_form_json
from .command_processor import CommandProcessor


class TelegramOperatorClient:
    def __init__(self) -> None:
        load_env_file()
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        allowed = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
        self.allowed_chat_ids = {item.strip() for item in allowed.split(",") if item.strip()}
        if self.chat_id:
            self.allowed_chat_ids.add(str(self.chat_id))
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        self.cfg = load_live_config()
        self.offset_path = controls_paths(self.cfg)["telegram_offset"]
        self.processor = CommandProcessor(self.cfg)

    def configured(self) -> bool:
        return bool(self.token and self.allowed_chat_ids)

    def _load_offset(self) -> int:
        try:
            return int(self.offset_path.read_text().strip())
        except Exception:
            return 0

    def _save_offset(self, value: int) -> None:
        self.offset_path.parent.mkdir(parents=True, exist_ok=True)
        self.offset_path.write_text(str(value))

    def send_message(self, text: str, chat_id: str | None = None) -> dict[str, Any]:
        if not self.base_url:
            return {"ok": False, "reason": "telegram_not_configured"}
        target = chat_id or self.chat_id
        res = http_post_form_json(f"{self.base_url}/sendMessage", {"chat_id": target, "text": text})
        return {"ok": res.ok, "status": res.status, "data": res.data, "error": res.error}

    def get_updates(self, timeout: int = 20) -> dict[str, Any]:
        if not self.base_url:
            return {"ok": False, "reason": "telegram_not_configured"}
        offset = self._load_offset()
        res = http_get_json(f"{self.base_url}/getUpdates", params={"offset": offset, "timeout": timeout})
        if not res.ok:
            return {"ok": False, "status": res.status, "error": res.error}
        return {"ok": True, "updates": (res.data or {}).get("result") or []}

    def process_updates_once(self) -> dict[str, Any]:
        updates_res = self.get_updates(timeout=20)
        if not updates_res.get("ok"):
            return updates_res
        processed = []
        for update in updates_res.get("updates") or []:
            update_id = int(update.get("update_id", 0))
            message = update.get("message") or update.get("edited_message") or {}
            chat = message.get("chat") or {}
            chat_id = str(chat.get("id", ""))
            text = (message.get("text") or "").strip()
            if update_id:
                self._save_offset(update_id + 1)
            if not text:
                continue
            if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
                self.send_message("Unauthorized chat id.", chat_id=chat_id)
                processed.append({"chat_id": chat_id, "status": "unauthorized"})
                continue
            result = self.processor.process(text, source=f"telegram:{chat_id}")
            reply = json.dumps(result)
            self.send_message(reply, chat_id=chat_id)
            processed.append({"chat_id": chat_id, "command": text, "result": result})
        return {"ok": True, "processed": processed, "count": len(processed)}

    def run_forever(self) -> None:
        if not self.configured():
            raise RuntimeError("Telegram bot is not configured")
        poll_seconds = int(os.getenv("ROI_SNIPS_TELEGRAM_POLL_SECONDS", "15"))
        while True:
            self.process_updates_once()
            time.sleep(max(poll_seconds, 1))


if __name__ == "__main__":
    client = TelegramOperatorClient()
    if not client.configured():
        print(json.dumps({"ok": False, "reason": "telegram_not_configured"}))
        raise SystemExit(1)
    print(json.dumps(client.process_updates_once()))
