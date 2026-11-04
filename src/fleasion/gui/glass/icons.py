"""Line icons for the Glass navigation, drawn as vector paths on a 24-unit grid."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainterPath, QPen

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtGui import QColor, QPainter

_GRID: Final = 24.0


def _replacer(path: QPainterPath) -> None:
    # Two opposing arrows: swap one asset for another
    path.moveTo(4, 8)
    path.lineTo(17, 8)
    path.moveTo(13.5, 4.5)
    path.lineTo(17, 8)
    path.lineTo(13.5, 11.5)
    path.moveTo(20, 16)
    path.lineTo(7, 16)
    path.moveTo(10.5, 12.5)
    path.lineTo(7, 16)
    path.lineTo(10.5, 19.5)


def _scraper(path: QPainterPath) -> None:
    # Stacked layers: everything the cache collected
    path.moveTo(12, 3.5)
    path.lineTo(20.5, 8)
    path.lineTo(12, 12.5)
    path.lineTo(3.5, 8)
    path.closeSubpath()
    path.moveTo(3.5, 12)
    path.lineTo(12, 16.5)
    path.lineTo(20.5, 12)
    path.moveTo(3.5, 16)
    path.lineTo(12, 20.5)
    path.lineTo(20.5, 16)


def _modifications(path: QPainterPath) -> None:
    # Three sliders with offset knobs
    for y, knob in ((6.0, 9.0), (12.0, 15.0), (18.0, 7.0)):
        path.moveTo(4, y)
        path.lineTo(knob - 2.2, y)
        path.moveTo(knob + 2.2, y)
        path.lineTo(20, y)
        path.addEllipse(QPointF(knob, y), 2.2, 2.2)


def _subplace_joiner(path: QPainterPath) -> None:
    # Arrow entering a doorway
    path.moveTo(14, 4)
    path.lineTo(18, 4)
    path.quadTo(20, 4, 20, 6)
    path.lineTo(20, 18)
    path.quadTo(20, 20, 18, 20)
    path.lineTo(14, 20)
    path.moveTo(4, 12)
    path.lineTo(15, 12)
    path.moveTo(11, 8)
    path.lineTo(15, 12)
    path.lineTo(11, 16)


def _miscellaneous(path: QPainterPath) -> None:
    # A 2x2 grid of tiles
    for x in (4.0, 13.0):
        for y in (4.0, 13.0):
            path.addRoundedRect(QRectF(x, y, 7, 7), 1.8, 1.8)


def _proxy(path: QPainterPath) -> None:
    # Globe
    path.addEllipse(QPointF(12, 12), 8.5, 8.5)
    path.addEllipse(QPointF(12, 12), 3.6, 8.5)
    path.moveTo(3.5, 12)
    path.lineTo(20.5, 12)


def _settings(path: QPainterPath) -> None:
    # Gear: eight trapezoidal teeth around a hub
    teeth = 8
    inner, outer = 7.0, 9.6
    points: list[QPointF] = []
    for tooth in range(teeth):
        centre = tooth * 2 * math.pi / teeth
        for offset, radius in ((-0.30, inner), (-0.16, outer), (0.16, outer), (0.30, inner)):
            angle = centre + offset
            points.append(QPointF(12 + radius * math.cos(angle), 12 + radius * math.sin(angle)))
    path.moveTo(points[0])
    for point in points[1:]:
        path.lineTo(point)
    path.closeSubpath()
    path.addEllipse(QPointF(12, 12), 3, 3)


def _fallback(path: QPainterPath) -> None:
    path.addEllipse(QPointF(12, 12), 3.5, 3.5)


_ICONS: Final[dict[str, Callable[[QPainterPath], None]]] = {
    'replacer': _replacer,
    'scraper': _scraper,
    'modifications': _modifications,
    'subplace_joiner': _subplace_joiner,
    'miscellaneous': _miscellaneous,
    'proxy': _proxy,
    'settings': _settings,
}


def paint_icon(painter: QPainter, name: str, rect: QRectF, color: QColor) -> None:
    """Stroke the named icon, scaled to fit ``rect``."""
    path = QPainterPath()
    _ICONS.get(name, _fallback)(path)
    scale = min(rect.width(), rect.height()) / _GRID
    painter.save()
    painter.translate(rect.center())
    painter.scale(scale, scale)
    painter.translate(-_GRID / 2, -_GRID / 2)
    pen = QPen(color, 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCosmetic(False)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.restore()
