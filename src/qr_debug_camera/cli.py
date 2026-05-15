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
from qr_debug_camera.injection import load_injected_camera_script
from qr_debug_camera.logger import QrLogger
from qr_debug_camera.overlay import OverlayWindow
from qr_debug_camera.stream import BrowserFramePusher, FrameWorker


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
    pusher = None
    worker = None
    exit_requested = threading.Event()
    _start_exit_watcher(config.qr.exit_key, exit_requested)

    try:
        chrome.start()
        cdp = chrome.connect()
        injected = load_injected_camera_script(config)
        pusher = BrowserFramePusher(chrome, config, cdp, injected)
        pusher.install(navigate=True)

        capture = QrCapture(config.camera, config.qr)
        logger = QrLogger(config.qr)
        worker = FrameWorker(
            capture=capture,
            logger=logger,
            pusher=pusher,
            rect=overlay.capture_rect(),
            capture_fps=config.camera.capture_fps,
        )
        worker.start()

        def tick() -> None:
            if exit_requested.is_set():
                app.quit()

        timer = QTimer()
        timer.timeout.connect(tick)
        timer.start(100)
        return app.exec()
    except KeyboardInterrupt:
        return 130
    finally:
        if worker:
            worker.stop(timeout_seconds=8.0)
        if pusher:
            pusher.close()
        else:
            chrome.stop(cdp)
            if cdp:
                try:
                    cdp.close()
                except Exception:
                    pass
