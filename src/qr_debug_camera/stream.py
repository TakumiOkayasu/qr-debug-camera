from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from qr_debug_camera.capture import QrCapture
from qr_debug_camera.cdp import CdpClient
from qr_debug_camera.chrome import ChromeController
from qr_debug_camera.config import AppConfig
from qr_debug_camera.geometry import ScreenRect
from qr_debug_camera.injection import frame_expression
from qr_debug_camera.logger import QrLogger


@dataclass
class BrowserFramePusher:
    chrome: ChromeController
    config: AppConfig
    cdp: CdpClient
    injected_script: str

    def install(self, *, navigate: bool) -> None:
        self.cdp.send("Page.enable")
        self.cdp.send("Runtime.enable")
        self.cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": self.injected_script})
        self.cdp.send(
            "Runtime.evaluate",
            {"expression": self.injected_script, "awaitPromise": False},
        )
        if navigate:
            self.cdp.send("Page.navigate", {"url": self.config.chrome.target_url})

    def push(self, frame: dict[str, Any]) -> None:
        try:
            self._send_frame(frame)
            return
        except Exception:
            pass

        self.reconnect()
        self._send_frame(frame)

    def reconnect(self) -> None:
        try:
            self.cdp.close()
        except Exception:
            pass
        self.cdp = self.chrome.connect(timeout_seconds=3.0)
        self.install(navigate=False)

    def close(self) -> None:
        self.chrome.stop(self.cdp)
        try:
            self.cdp.close()
        except Exception:
            pass

    def _send_frame(self, frame: dict[str, Any]) -> None:
        self.cdp.send(
            "Runtime.evaluate",
            {"expression": frame_expression(frame), "awaitPromise": False},
        )


@dataclass
class FrameWorker:
    capture: QrCapture
    logger: QrLogger
    pusher: BrowserFramePusher
    rect: ScreenRect
    capture_fps: int

    def __post_init__(self) -> None:
        self._stop_requested = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout_seconds: float = 3.0) -> None:
        self._stop_requested.set()
        self._thread.join(timeout=timeout_seconds)

    def _run(self) -> None:
        interval = 1 / max(1, self.capture_fps)

        while not self._stop_requested.is_set():
            started_at = time.monotonic()
            try:
                frame = self.capture.capture(self.rect)
                if frame.get("status") == "ok" and isinstance(frame.get("payload"), str):
                    self.logger.log(frame["payload"], str(frame["capturedAt"]))
                self.pusher.push(frame)
            except Exception as error:
                print(error, flush=True)

            elapsed = time.monotonic() - started_at
            self._stop_requested.wait(max(0.0, interval - elapsed))
