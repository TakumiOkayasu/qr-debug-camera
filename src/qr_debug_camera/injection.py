from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from qr_debug_camera.config import AppConfig


def load_injected_camera_script(config: AppConfig) -> str:
    asset = files("qr_debug_camera.assets").joinpath("injected-camera.js")
    script = asset.read_text(encoding="utf-8")
    options: dict[str, Any] = {
        "width": config.camera.width,
        "height": config.camera.height,
        "fps": config.camera.fps,
        "zoomMax": config.camera.detect_zoom_max,
        "label": config.camera.device_label,
        "deviceId": "qr-debug-camera",
    }
    return f"globalThis.__QR_DEBUG_CAMERA_OPTIONS__ = {json.dumps(options)};\n{script}"


def frame_expression(frame: dict[str, Any]) -> str:
    return (
        "globalThis.__qrDebugCameraFrame && "
        f"globalThis.__qrDebugCameraFrame({json.dumps(frame, ensure_ascii=False)});"
    )
