from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import cv2
import mss
import numpy as np
import zxingcpp

from qr_debug_camera.codec import decode_qr_bytes
from qr_debug_camera.config import CameraConfig, QrConfig
from qr_debug_camera.geometry import ScreenRect
from qr_debug_camera.logger import timestamp


def _encode_png_data_url(image: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Failed to encode PNG frame")
    data = base64.b64encode(buffer.tobytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _letterbox(image: np.ndarray, width: int, height: int) -> np.ndarray:
    source_height, source_width = image.shape[:2]
    if source_width <= 0 or source_height <= 0:
        return _blank_image(width, height)

    ratio = min(width / source_width, height / source_height)
    resized_width = max(1, int(source_width * ratio))
    resized_height = max(1, int(source_height * ratio))
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    x = (width - resized_width) // 2
    y = (height - resized_height) // 2
    canvas[y : y + resized_height, x : x + resized_width] = resized
    return canvas


def _blank_image(width: int, height: int) -> np.ndarray:
    return np.zeros((height, width, 3), dtype=np.uint8)


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
    if right <= left or bottom <= top:
        return image
    return image[top:bottom, left:right]


def _zxing_points(barcode: Any) -> np.ndarray:
    position = barcode.position
    return np.array(
        [
            [position.top_left.x, position.top_left.y],
            [position.top_right.x, position.top_right.y],
            [position.bottom_right.x, position.bottom_right.y],
            [position.bottom_left.x, position.bottom_left.y],
        ],
        dtype=np.float32,
    )


@dataclass
class QrCapture:
    camera: CameraConfig
    qr: QrConfig

    def __post_init__(self) -> None:
        self._screen = mss.mss()
        self._detector = cv2.QRCodeDetector()
        self._last_image: np.ndarray | None = None

    def _reset_screen(self) -> None:
        try:
            next_screen = mss.mss()
        except Exception:
            return

        try:
            self._screen.close()
        except Exception:
            pass
        self._screen = next_screen

    def _miss_frame(self, captured_at: str, image: np.ndarray | None = None) -> dict[str, Any]:
        frame = image if image is not None else _blank_image(self.camera.width, self.camera.height)
        return {
            "status": "miss",
            "imageDataUrl": _encode_png_data_url(
                _letterbox(frame, self.camera.width, self.camera.height)
            ),
            "capturedAt": captured_at,
        }

    def capture(self, rect: ScreenRect) -> dict[str, Any]:
        captured_at = timestamp(self.qr.timezone)
        monitor = {
            "left": rect.x,
            "top": rect.y,
            "width": rect.width,
            "height": rect.height,
        }

        try:
            shot = self._screen.grab(monitor)
        except Exception:
            self._reset_screen()
            return self._miss_frame(captured_at, self._last_image)

        bgra = np.asarray(shot)
        bgr = cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
        self._last_image = bgr

        try:
            barcode = zxingcpp.read_barcode(
                bgr,
                formats=zxingcpp.QRCode,
                text_mode=zxingcpp.TextMode.Plain,
            )
        except Exception:
            barcode = None

        if barcode and barcode.valid:
            payload = decode_qr_bytes(bytes(barcode.bytes), self.qr.encodings)
            qr_image = _crop_by_points(bgr, _zxing_points(barcode))
            return {
                "status": "ok",
                "imageDataUrl": _encode_png_data_url(qr_image),
                "capturedAt": captured_at,
                "payload": payload,
            }

        try:
            payload, points, _ = self._detector.detectAndDecode(bgr)
        except (UnicodeError, cv2.error):
            payload, points = "", None

        if payload and points is not None:
            qr_image = _crop_by_points(bgr, points.reshape(-1, 2))
            return {
                "status": "ok",
                "imageDataUrl": _encode_png_data_url(qr_image),
                "capturedAt": captured_at,
                "payload": payload,
            }

        return self._miss_frame(captured_at, bgr)
