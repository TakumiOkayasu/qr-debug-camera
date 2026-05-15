from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenRect:
    x: int
    y: int
    width: int
    height: int
