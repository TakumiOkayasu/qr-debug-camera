from __future__ import annotations

import importlib
import os
import threading
import time
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from qr_debug_camera.capture import QrCapture
from qr_debug_camera.chrome import ChromeController
from qr_debug_camera.config import load_config
from qr_debug_camera.injection import frame_expression, load_injected_camera_script
from qr_debug_camera.logger import QrLogger
from qr_debug_camera.overlay import OverlayWindow


def _start_exit_watcher(exit_key: str, exit_requested: threading.Event) -> None:
    def watch_windows_console() -> None:
        msvcrt: Any = importlib.import_module("msvcrt")

        while not exit_requested.is_set():
            if msvcrt.kbhit():
                char = msvcrt.getwch()
                if char.lower() == exit_key.lower():
                    exit_requested.set()
                    return
            time.sleep(0.05)

    if os.name == "nt" and exit_key:
        thread = threading.Thread(target=watch_windows_console, daemon=True)
        thread.start()


def main(argv: list[str] | None = None) -> int:
    config = load_config(argv)
    app = QApplication([])
    overlay = OverlayWindow(config.overlay)
    overlay.show()

    chrome = ChromeController(config)
    cdp = None
    exit_requested = threading.Event()
    _start_exit_watcher(config.qr.exit_key, exit_requested)

    try:
        chrome.start()
        cdp = chrome.connect()
        injected = load_injected_camera_script(config)
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": injected})
        cdp.send("Runtime.evaluate", {"expression": injected, "awaitPromise": False})
        cdp.send("Page.navigate", {"url": config.chrome.target_url})

        capture = QrCapture(config.camera, config.qr)
        logger = QrLogger(config.qr)
        busy = False

        def tick() -> None:
            nonlocal busy
            if exit_requested.is_set():
                app.quit()
                return
            if busy:
                return

            busy = True
            try:
                frame: dict[str, Any] = capture.capture(overlay.capture_rect())
                if frame.get("status") == "ok" and isinstance(frame.get("payload"), str):
                    logger.log(frame["payload"], str(frame["capturedAt"]))
                cdp.send(
                    "Runtime.evaluate",
                    {"expression": frame_expression(frame), "awaitPromise": False},
                )
            except Exception as error:
                print(error, flush=True)
            finally:
                busy = False

        timer = QTimer()
        timer.timeout.connect(tick)
        timer.start(max(1, int(1000 / config.camera.capture_fps)))
        return app.exec()
    except KeyboardInterrupt:
        return 130
    finally:
        if cdp:
            cdp.close()
        chrome.stop()
