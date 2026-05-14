from __future__ import annotations

import argparse
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ChromeConfig:
    target_url: str
    profile_dir: Path
    remote_debugging_port: int
    path: str


@dataclass(frozen=True)
class OverlayConfig:
    width: int
    height: int
    border: int
    always_on_top: bool
    click_through: bool


@dataclass(frozen=True)
class CameraConfig:
    width: int
    height: int
    fps: int
    capture_fps: int
    detect_zoom_max: float
    device_label: str


@dataclass(frozen=True)
class QrConfig:
    log_path: Path
    timezone: str
    dedupe_ms: int
    exit_key: str


@dataclass(frozen=True)
class AppConfig:
    chrome: ChromeConfig
    overlay: OverlayConfig
    camera: CameraConfig
    qr: QrConfig


def _string(value: Any, fallback: str) -> str:
    return value if isinstance(value, str) else fallback


def _int(value: Any, fallback: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        return int(value)
    return fallback


def _float(value: Any, fallback: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value.strip():
        return float(value)
    return fallback


def _bool(value: Any, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback


def _path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base_dir / path


def load_config(argv: list[str] | None = None) -> AppConfig:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--url")
    parser.add_argument("--fps", type=int)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--chrome-path")
    args = parser.parse_args(argv)

    config_path = Path(args.config).expanduser().resolve()
    base_dir = config_path.parent
    raw: dict[str, Any] = {}
    if config_path.exists():
        with config_path.open("rb") as file:
            raw = tomllib.load(file)

    chrome = raw.get("chrome", {})
    overlay = raw.get("overlay", {})
    camera = raw.get("camera", {})
    qr = raw.get("qr", {})

    chrome_config = ChromeConfig(
        target_url=args.url or _string(chrome.get("target_url"), "https://example.com"),
        profile_dir=_path(_string(chrome.get("profile_dir"), ".runtime/chrome-profile"), base_dir),
        remote_debugging_port=_int(chrome.get("remote_debugging_port"), 9222),
        path=args.chrome_path or _string(chrome.get("path"), ""),
    )
    overlay_config = OverlayConfig(
        width=_int(overlay.get("width"), 720),
        height=_int(overlay.get("height"), 720),
        border=_int(overlay.get("border"), 4),
        always_on_top=_bool(overlay.get("always_on_top"), True),
        click_through=_bool(overlay.get("click_through"), True),
    )
    camera_config = CameraConfig(
        width=args.width or _int(camera.get("width"), 1280),
        height=args.height or _int(camera.get("height"), 720),
        fps=args.fps or _int(camera.get("fps"), 30),
        capture_fps=args.fps or _int(camera.get("capture_fps"), 15),
        detect_zoom_max=_float(camera.get("detect_zoom_max"), 0.8),
        device_label=_string(camera.get("device_label"), "QR Debug Camera"),
    )
    qr_config = QrConfig(
        log_path=_path(_string(qr.get("log_path"), "logs/qr-readings.jsonl"), base_dir),
        timezone=_string(qr.get("timezone"), "Asia/Tokyo"),
        dedupe_ms=_int(qr.get("dedupe_ms"), 1000),
        exit_key=_string(qr.get("exit_key"), "q"),
    )
    return AppConfig(
        chrome=chrome_config,
        overlay=overlay_config,
        camera=camera_config,
        qr=qr_config,
    )
