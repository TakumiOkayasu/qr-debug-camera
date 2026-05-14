from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from qr_debug_camera.config import OverlayConfig


class OverlayWindow(QWidget):
    def __init__(self, config: OverlayConfig) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if config.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint

        super().__init__(None, flags)
        self.config = config
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if config.click_through:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        screen = QApplication.primaryScreen()
        geometry = screen.geometry()
        x = geometry.x() + (geometry.width() - config.width) // 2
        y = geometry.y() + (geometry.height() - config.height) // 2
        self.setGeometry(x, y, config.width, config.height)

    def capture_rect(self) -> QRect:
        geometry = self.geometry()
        border = self.config.border
        return QRect(
            geometry.x() + border,
            geometry.y() + border,
            max(1, geometry.width() - border * 2),
            max(1, geometry.height() - border * 2),
        )

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(0, 180, 255, 235), self.config.border)
        painter.setPen(pen)
        inset = self.config.border / 2
        painter.drawRect(
            int(inset),
            int(inset),
            int(self.width() - self.config.border),
            int(self.height() - self.config.border),
        )
