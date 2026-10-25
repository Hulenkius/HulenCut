"""Small Photoshop-like line icons drawn at runtime.

Keeping the icons vector-like and theme-aware avoids shipping a large icon
theme while still giving the toolbar a consistent monochrome appearance.
"""

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QIconEngine,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)


def _pixmap(name: str, color: str, accent: str, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.scale(size / 24.0, size / 24.0)

    pen = QPen(QColor(color), 1.6)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    accent_pen = QPen(QColor(accent), 1.8)
    accent_pen.setCapStyle(Qt.RoundCap)
    accent_pen.setJoinStyle(Qt.RoundJoin)

    if name == "image":
        painter.drawRoundedRect(QRectF(2.5, 4.0, 19.0, 16.0), 2.0, 2.0)
        painter.drawEllipse(QPointF(16.5, 8.0), 2.0, 2.0)
        path = QPainterPath(QPointF(4.0, 17.0))
        path.lineTo(9.5, 11.5)
        path.lineTo(13.0, 15.0)
        path.lineTo(16.0, 12.0)
        path.lineTo(20.0, 16.0)
        painter.drawPath(path)
    elif name == "folder":
        path = QPainterPath(QPointF(2.5, 7.0))
        path.lineTo(9.0, 7.0)
        path.lineTo(11.0, 4.5)
        path.lineTo(21.0, 4.5)
        path.lineTo(21.0, 19.0)
        path.lineTo(3.0, 19.0)
        path.lineTo(3.0, 7.0)
        painter.drawPath(path)
        painter.drawLine(QPointF(3.0, 9.0), QPointF(21.0, 9.0))
    elif name == "project":
        path = QPainterPath(QPointF(5.0, 2.5))
        path.lineTo(14.0, 2.5)
        path.lineTo(19.0, 7.5)
        path.lineTo(19.0, 21.5)
        path.lineTo(5.0, 21.5)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(14.0, 3.0), QPointF(14.0, 8.0))
        painter.drawLine(QPointF(14.0, 8.0), QPointF(19.0, 8.0))
        painter.drawLine(QPointF(8.0, 12.0), QPointF(16.0, 12.0))
        painter.drawLine(QPointF(8.0, 15.5), QPointF(16.0, 15.5))
    elif name == "save":
        painter.drawRoundedRect(QRectF(3.0, 3.0, 18.0, 18.0), 2.0, 2.0)
        painter.drawRect(QRectF(7.0, 3.5, 9.0, 6.0))
        painter.drawRoundedRect(QRectF(6.0, 13.0, 12.0, 7.5), 1.5, 1.5)
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(10.0, 5.5), QPointF(13.5, 5.5))
    elif name == "export":
        painter.drawLine(QPointF(12.0, 3.0), QPointF(12.0, 14.0))
        painter.drawLine(QPointF(8.0, 7.0), QPointF(12.0, 3.0))
        painter.drawLine(QPointF(12.0, 3.0), QPointF(16.0, 7.0))
        path = QPainterPath(QPointF(4.0, 12.0))
        path.lineTo(4.0, 20.0)
        path.lineTo(20.0, 20.0)
        path.lineTo(20.0, 12.0)
        painter.drawPath(path)
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(8.0, 17.0), QPointF(16.0, 17.0))
    elif name == "wand":
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(4.0, 20.0), QPointF(15.0, 9.0))
        painter.drawLine(QPointF(13.0, 7.0), QPointF(17.0, 11.0))
        painter.setPen(pen)
        painter.drawLine(QPointF(6.0, 5.0), QPointF(6.0, 8.0))
        painter.drawLine(QPointF(4.5, 6.5), QPointF(7.5, 6.5))
        painter.drawLine(QPointF(18.0, 3.0), QPointF(18.0, 6.0))
        painter.drawLine(QPointF(16.5, 4.5), QPointF(19.5, 4.5))
        painter.drawLine(QPointF(19.0, 13.0), QPointF(19.0, 15.0))
    elif name == "table":
        painter.drawRect(QRectF(3.0, 4.0, 18.0, 16.0))
        for x in (9.0, 15.0):
            painter.drawLine(QPointF(x, 4.0), QPointF(x, 20.0))
        for y in (9.0, 14.0):
            painter.drawLine(QPointF(3.0, y), QPointF(21.0, y))
        painter.setPen(accent_pen)
        painter.drawRect(QRectF(3.0, 4.0, 6.0, 5.0))
    elif name == "grid":
        # Four independent slice outlines crossed by a blue dividing axis.
        for x in (2.8, 13.4):
            for y in (2.8, 13.4):
                painter.drawRoundedRect(QRectF(x, y, 7.8, 7.8), 1.1, 1.1)
        divide_pen = QPen(QColor(accent), 2.4)
        divide_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(divide_pen)
        painter.drawLine(QPointF(12.0, 1.2), QPointF(12.0, 22.8))
        painter.drawLine(QPointF(1.2, 12.0), QPointF(22.8, 12.0))
    elif name == "move":
        painter.drawLine(QPointF(12.0, 3.0), QPointF(12.0, 21.0))
        painter.drawLine(QPointF(3.0, 12.0), QPointF(21.0, 12.0))
        painter.drawLine(QPointF(12.0, 3.0), QPointF(9.0, 6.0))
        painter.drawLine(QPointF(12.0, 3.0), QPointF(15.0, 6.0))
        painter.drawLine(QPointF(12.0, 21.0), QPointF(9.0, 18.0))
        painter.drawLine(QPointF(12.0, 21.0), QPointF(15.0, 18.0))
        painter.drawLine(QPointF(3.0, 12.0), QPointF(6.0, 9.0))
        painter.drawLine(QPointF(3.0, 12.0), QPointF(6.0, 15.0))
        painter.drawLine(QPointF(21.0, 12.0), QPointF(18.0, 9.0))
        painter.drawLine(QPointF(21.0, 12.0), QPointF(18.0, 15.0))
        painter.setPen(accent_pen)
        painter.drawEllipse(QPointF(12.0, 12.0), 2.2, 2.2)
    elif name == "scale":
        painter.drawRect(QRectF(4.0, 4.0, 16.0, 16.0))
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(15.0, 9.0), QPointF(20.0, 4.0))
        painter.drawLine(QPointF(16.0, 4.0), QPointF(20.0, 4.0))
        painter.drawLine(QPointF(20.0, 4.0), QPointF(20.0, 8.0))
        painter.drawLine(QPointF(9.0, 15.0), QPointF(4.0, 20.0))
    elif name == "ruler":
        painter.save()
        painter.translate(12.0, 12.0)
        painter.rotate(-45)
        painter.drawRect(QRectF(-9.0, -4.0, 18.0, 8.0))
        for x in (-5.0, -1.0, 3.0, 7.0):
            painter.drawLine(QPointF(x, -4.0), QPointF(x, 0.0))
        painter.restore()
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(4.0, 20.0), QPointF(20.0, 4.0))
    elif name == "filter":
        path = QPainterPath(QPointF(3.0, 4.0))
        path.lineTo(21.0, 4.0)
        path.lineTo(14.0, 12.0)
        path.lineTo(14.0, 20.0)
        path.lineTo(10.0, 18.0)
        path.lineTo(10.0, 12.0)
        path.closeSubpath()
        painter.drawPath(path)
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(6.0, 7.0), QPointF(18.0, 7.0))
    elif name == "frame":
        for start, end in (
            ((3.0, 8.0), (3.0, 3.0)), ((3.0, 3.0), (8.0, 3.0)),
            ((16.0, 3.0), (21.0, 3.0)), ((21.0, 3.0), (21.0, 8.0)),
            ((3.0, 16.0), (3.0, 21.0)), ((3.0, 21.0), (8.0, 21.0)),
            ((16.0, 21.0), (21.0, 21.0)), ((21.0, 21.0), (21.0, 16.0)),
        ):
            painter.drawLine(QPointF(*start), QPointF(*end))
        painter.setPen(accent_pen)
        painter.drawRect(QRectF(8.0, 8.0, 8.0, 8.0))
    elif name == "merge":
        painter.drawRect(QRectF(4.0, 4.0, 11.0, 11.0))
        painter.setPen(accent_pen)
        painter.drawRect(QRectF(9.0, 9.0, 11.0, 11.0))
    elif name == "ocr-text":
        painter.drawRoundedRect(QRectF(2.5, 4.0, 19.0, 16.0), 2.0, 2.0)
        painter.drawLine(QPointF(6.0, 8.5), QPointF(13.0, 8.5))
        painter.drawLine(QPointF(6.0, 12.0), QPointF(17.0, 12.0))
        painter.drawLine(QPointF(6.0, 15.5), QPointF(11.0, 15.5))
        painter.setPen(accent_pen)
        painter.drawEllipse(QPointF(16.0, 15.5), 2.3, 2.3)
        painter.drawLine(QPointF(17.7, 17.2), QPointF(20.5, 20.0))
    elif name == "text":
        painter.drawLine(QPointF(5.0, 18.0), QPointF(12.0, 5.0))
        painter.drawLine(QPointF(12.0, 5.0), QPointF(19.0, 18.0))
        painter.drawLine(QPointF(8.0, 13.0), QPointF(16.0, 13.0))
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(20.0, 15.0), QPointF(20.0, 21.0))
    elif name == "command":
        painter.drawRoundedRect(QRectF(3.0, 4.0, 18.0, 16.0), 2.0, 2.0)
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(6.5, 8.0), QPointF(9.5, 12.0))
        painter.drawLine(QPointF(9.5, 12.0), QPointF(6.5, 16.0))
        painter.setPen(pen)
        painter.drawLine(QPointF(12.0, 9.0), QPointF(18.0, 9.0))
        painter.drawLine(QPointF(12.0, 13.0), QPointF(17.0, 13.0))
        painter.drawLine(QPointF(12.0, 17.0), QPointF(16.0, 17.0))
    elif name in ("zoom-in", "zoom-out"):
        painter.drawEllipse(QPointF(10.0, 10.0), 6.0, 6.0)
        painter.drawLine(QPointF(14.5, 14.5), QPointF(21.0, 21.0))
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(7.0, 10.0), QPointF(13.0, 10.0))
        if name != "zoom-out":
            painter.drawLine(QPointF(10.0, 7.0), QPointF(10.0, 13.0))
    elif name == "settings":
        for y, x1, x2 in ((7.0, 4.0, 20.0), (12.0, 4.0, 20.0), (17.0, 4.0, 20.0)):
            painter.drawLine(QPointF(x1, y), QPointF(x2, y))
        painter.setPen(accent_pen)
        painter.drawEllipse(QPointF(9.0, 7.0), 2.0, 2.0)
        painter.drawEllipse(QPointF(15.0, 12.0), 2.0, 2.0)
        painter.drawEllipse(QPointF(8.0, 17.0), 2.0, 2.0)
    elif name == "theme":
        painter.drawEllipse(QPointF(12.0, 12.0), 8.0, 8.0)
        path = QPainterPath()
        path.moveTo(12.0, 4.0)
        path.arcTo(QRectF(4.0, 4.0, 16.0, 16.0), 90.0, -180.0)
        path.closeSubpath()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(accent))
        painter.drawPath(path)
    elif name == "language":
        painter.drawEllipse(QPointF(12.0, 12.0), 8.5, 8.5)
        painter.drawEllipse(QPointF(12.0, 12.0), 4.0, 8.5)
        painter.drawLine(QPointF(3.5, 12.0), QPointF(20.5, 12.0))
        painter.setPen(accent_pen)
        painter.drawArc(QRectF(4.0, 5.0, 16.0, 14.0), 20 * 16, 140 * 16)
    elif name == "help":
        painter.drawEllipse(QPointF(12.0, 12.0), 9.0, 9.0)
        painter.setPen(accent_pen)
        path = QPainterPath(QPointF(9.0, 9.0))
        path.cubicTo(9.0, 5.0, 16.0, 5.0, 16.0, 10.0)
        path.cubicTo(16.0, 13.0, 12.0, 13.0, 12.0, 16.0)
        painter.drawPath(path)
        painter.drawPoint(QPointF(12.0, 19.0))
    elif name == "info":
        painter.drawEllipse(QPointF(12.0, 12.0), 9.0, 9.0)
        painter.setPen(accent_pen)
        painter.drawPoint(QPointF(12.0, 7.0))
        painter.drawLine(QPointF(12.0, 10.0), QPointF(12.0, 17.0))
    elif name == "update":
        painter.drawArc(QRectF(4.0, 4.0, 16.0, 16.0), 30 * 16, 280 * 16)
        painter.drawLine(QPointF(18.0, 4.0), QPointF(20.0, 8.0))
        painter.drawLine(QPointF(20.0, 8.0), QPointF(16.0, 9.0))
        painter.setPen(accent_pen)
        painter.drawPoint(QPointF(12.0, 12.0))
    elif name == "manual":
        path = QPainterPath(QPointF(3.0, 5.0))
        path.cubicTo(7.0, 3.0, 10.0, 4.0, 12.0, 6.0)
        path.cubicTo(14.0, 4.0, 17.0, 3.0, 21.0, 5.0)
        path.lineTo(21.0, 19.0)
        path.cubicTo(17.0, 17.0, 14.0, 18.0, 12.0, 20.0)
        path.cubicTo(10.0, 18.0, 7.0, 17.0, 3.0, 19.0)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(12.0, 6.0), QPointF(12.0, 20.0))
    elif name == "chevron-left":
        painter.drawLine(QPointF(15.0, 5.0), QPointF(8.0, 12.0))
        painter.drawLine(QPointF(8.0, 12.0), QPointF(15.0, 19.0))
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(19.0, 6.0), QPointF(19.0, 18.0))
    elif name == "chevron-right":
        painter.drawLine(QPointF(9.0, 5.0), QPointF(16.0, 12.0))
        painter.drawLine(QPointF(16.0, 12.0), QPointF(9.0, 19.0))
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(5.0, 6.0), QPointF(5.0, 18.0))
    elif name in ("to-top", "up", "down", "to-bottom"):
        if name in ("to-top", "to-bottom"):
            line_y = 4.0 if name == "to-top" else 20.0
            painter.drawLine(QPointF(5.0, line_y), QPointF(19.0, line_y))
        if name in ("to-top", "up"):
            painter.drawLine(QPointF(12.0, 20.0), QPointF(12.0, 8.0))
            painter.drawLine(QPointF(12.0, 8.0), QPointF(8.0, 12.0))
            painter.drawLine(QPointF(12.0, 8.0), QPointF(16.0, 12.0))
        else:
            painter.drawLine(QPointF(12.0, 4.0), QPointF(12.0, 16.0))
            painter.drawLine(QPointF(12.0, 16.0), QPointF(8.0, 12.0))
            painter.drawLine(QPointF(12.0, 16.0), QPointF(16.0, 12.0))
        painter.setPen(accent_pen)
        painter.drawPoint(QPointF(12.0, 12.0))
    elif name == "clear-text":
        painter.drawLine(QPointF(5.0, 18.0), QPointF(11.0, 6.0))
        painter.drawLine(QPointF(11.0, 6.0), QPointF(17.0, 18.0))
        painter.drawLine(QPointF(7.0, 14.0), QPointF(15.0, 14.0))
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(4.0, 20.0), QPointF(20.0, 4.0))
    elif name == "trash":
        painter.drawLine(QPointF(5.0, 7.0), QPointF(19.0, 7.0))
        painter.drawLine(QPointF(9.0, 4.0), QPointF(15.0, 4.0))
        painter.drawRect(QRectF(7.0, 7.0, 10.0, 13.0))
        painter.drawLine(QPointF(10.0, 10.0), QPointF(10.0, 17.0))
        painter.drawLine(QPointF(14.0, 10.0), QPointF(14.0, 17.0))
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(8.0, 7.0), QPointF(9.0, 20.0))
    elif name == "crop":
        painter.drawLine(QPointF(7.0, 3.0), QPointF(7.0, 17.0))
        painter.drawLine(QPointF(7.0, 17.0), QPointF(21.0, 17.0))
        painter.setPen(accent_pen)
        painter.drawLine(QPointF(3.0, 7.0), QPointF(17.0, 7.0))
        painter.drawLine(QPointF(17.0, 7.0), QPointF(17.0, 21.0))
    elif name == "straighten":
        painter.drawLine(QPointF(4.0, 19.0), QPointF(20.0, 5.0))
        painter.drawLine(QPointF(10.0, 19.0), QPointF(20.0, 19.0))
        painter.drawArc(QRectF(10.0, 10.0, 10.0, 10.0), 270 * 16, 90 * 16)
        painter.setPen(accent_pen)
        painter.drawPoint(QPointF(4.0, 19.0))
    else:
        painter.drawEllipse(QPointF(12.0, 12.0), 8.0, 8.0)

    painter.end()
    return pixmap


class _LineIconEngine(QIconEngine):
    """Render line icons at the exact requested device resolution."""

    def __init__(self, name: str, dark: bool):
        super().__init__()
        self.name = name
        self.dark = dark

    def clone(self):
        return _LineIconEngine(self.name, self.dark)

    def _colors(self, mode):
        if mode == QIcon.Disabled:
            return ("#6f6f6f", "#5c6f88") if self.dark else ("#a0a0a0", "#7c9bc2")
        if self.dark:
            return "#d8d8d8", "#2680eb"
        return "#2b2b2b", "#1473e6"

    def scaledPixmap(self, size: QSize, mode, state, scale: float):
        color, accent = self._colors(mode)
        pixel_size = max(1, round(max(size.width(), size.height()) * scale))
        pixmap = _pixmap(self.name, color, accent, pixel_size)
        pixmap.setDevicePixelRatio(scale)
        return pixmap

    def pixmap(self, size: QSize, mode, state):
        screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen is not None else 1.0
        return self.scaledPixmap(size, mode, state, dpr)

    def paint(self, painter, rect, mode, state):
        color, accent = self._colors(mode)
        try:
            device_dpr = painter.device().devicePixelRatio()
        except Exception:
            device_dpr = 1.0
        pixel_size = max(1, round(max(rect.width(), rect.height()) * device_dpr))
        pixmap = _pixmap(self.name, color, accent, pixel_size)
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawPixmap(rect, pixmap, QRectF(pixmap.rect()))
        painter.restore()


def make_icon(name: str, dark: bool = True) -> QIcon:
    """Build a high-DPI aware, theme-sensitive line icon."""
    return QIcon(_LineIconEngine(name, dark))
