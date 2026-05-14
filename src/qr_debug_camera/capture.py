from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import cv2
import mss
import numpy as np
from PySide6.QtCore import QRect

from qr_debug_camera.config import CameraConfig, QrConfig
from qr_debug_camera.logger import timestamp


def _encode_png_data_url(image: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Failed to encode PNG frame")
    data = base64.b64encode(buffer.tobytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _letterbox(image: np.ndarray, width: int, height: int) -> np.ndarray:
    source_height, source_width = image.shape[:2]
    ratio = min(width / source_width, height / source_height)
    resized_width = max(1, int(source_width * ratio))
    resized_height = max(1, int(source_height * ratio))
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    x = (width - resized_width) // 2
    y = (height - resized_height) // 2
    canvas[y : y + resized_height, x : x + resized_width] = resized
    return canvas


def _crop_by_points(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    xs = points[:, 0]
    ys = points[:, 1]
    min_x = int(np.floor(xs.min()))
    max_x = int(np.ceil(xs.max()))
    min_y = int(np.floor(ys.min()))
    max_y = int(np.ceil(ys.max()))
    size = max(max_x - min_x, max_y - min_y)
    margin = int(size * 0.18)

    left = max(0, min_x - margin)
    top = max(0, min_y - margin)
    right = min(width, max_x + margin)
    bottom = min(height, max_y + margin)
    return image[top:bottom, left:right]


@dataclass
class QrCapture:
    camera: CameraConfig
    qr: QrConfig

    def __post_init__(self) -> None:
        self._screen = mss.mss()
        self._detector = cv2.QRCodeDetector()

    def capture(self, rect: QRect) -> dict[str, Any]:
        monitor = {
            "left": rect.x(),
            "top": rect.y(),
            "width": rect.width(),
            "height": rect.height(),
        }
        shot = self._screen.grab(monitor)
        bgra = np.asarray(shot)
        bgr = cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
        payload, points, _ = self._detector.detectAndDecode(bgr)
        captured_at = timestamp(self.qr.timezone)

        if payload and points is not None:
            qr_image = _crop_by_points(bgr, points.reshape(-1, 2))
            return {
                "status": "ok",
                "imageDataUrl": _encode_png_data_url(qr_image),
                "capturedAt": captured_at,
                "payload": payload,
            }

        return {
            "status": "miss",
            "imageDataUrl": _encode_png_data_url(
                _letterbox(bgr, self.camera.width, self.camera.height)
            ),
            "capturedAt": captured_at,
        }
