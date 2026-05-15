from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from qr_debug_camera.cdp import CdpClient
from qr_debug_camera.config import AppConfig

CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Chromium\Application\chrome.exe",
)


def _chrome_path(configured_path: str) -> str:
    if configured_path and Path(configured_path).exists():
        return configured_path
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return "chrome"


@dataclass
class ChromeController:
    config: AppConfig
    process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        self.config.chrome.profile_dir.mkdir(parents=True, exist_ok=True)
        args = [
            _chrome_path(self.config.chrome.path),
            f"--remote-debugging-port={self.config.chrome.remote_debugging_port}",
            f"--remote-allow-origins=http://127.0.0.1:{self.config.chrome.remote_debugging_port}",
            f"--user-data-dir={self.config.chrome.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--use-fake-ui-for-media-stream",
            "--new-window",
            "about:blank",
        ]
        self.process = subprocess.Popen(args)

    def connect(self, timeout_seconds: float = 15.0) -> CdpClient:
        websocket_url = self._wait_for_page_websocket_url(timeout_seconds=timeout_seconds)
        return CdpClient(websocket_url)

    def stop(self, cdp: CdpClient | None = None) -> None:
        if cdp:
            try:
                cdp.send_no_wait("Browser.close")
            except Exception:
                pass

        self._wait_for_exit(timeout_seconds=8.0)
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self._wait_for_exit(timeout_seconds=3.0)
        if self.process and self.process.poll() is None:
            self.process.kill()
            self._wait_for_exit(timeout_seconds=1.0)

    def _wait_for_exit(self, timeout_seconds: float) -> None:
        if not self.process:
            return

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                return
            time.sleep(0.05)

    def _wait_for_page_websocket_url(self, timeout_seconds: float = 15.0) -> str:
        deadline = time.monotonic() + timeout_seconds
        endpoint = f"http://127.0.0.1:{self.config.chrome.remote_debugging_port}/json/list"

        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(endpoint, timeout=1.0) as response:
                    targets = json.loads(response.read().decode("utf-8"))
                for target in targets:
                    if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                        return target["webSocketDebuggerUrl"]
            except OSError:
                pass
            time.sleep(0.25)

        raise TimeoutError(
            f"Chrome DevTools target was not available on port "
            f"{self.config.chrome.remote_debugging_port}"
        )
