from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from qr_debug_camera.config import QrConfig

FALLBACK_TIMEZONES: dict[str, tzinfo] = {
    "Asia/Tokyo": timezone(timedelta(hours=9), "JST"),
    "UTC": UTC,
}


def _timezone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return FALLBACK_TIMEZONES.get(name, datetime.now().astimezone().tzinfo or UTC)


def timestamp(timezone: str) -> str:
    return datetime.now(_timezone(timezone)).isoformat(timespec="milliseconds")


@dataclass
class QrLogger:
    config: QrConfig
    last_payload: str = ""
    last_logged_at_ms: int = 0

    def log(self, payload: str, captured_at: str) -> None:
        now_ms = int(datetime.now().timestamp() * 1000)
        if (
            payload == self.last_payload
            and now_ms - self.last_logged_at_ms < self.config.dedupe_ms
        ):
            return

        self.last_payload = payload
        self.last_logged_at_ms = now_ms

        Path(self.config.log_path).parent.mkdir(parents=True, exist_ok=True)
        record = {
            "captured_at": captured_at,
            "payload": payload,
            "source": "qr-debug-camera",
        }
        with Path(self.config.log_path).open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"{captured_at}\t{payload}", flush=True)
