"""Glass dashboard navigation: the tabs live in a pop-out panel on the left edge.

While Glass is active the dashboard's tab bar is hidden. A slim handle with a
chevron sits inside the window's left padding (it adds no width of its own) and
slides a navigation panel out over the content when hovered. The panel is
painted with the window's own glass, and the content fades behind it.

Pages can carry two properties: ``glassNavIcon`` names their icon (see
:mod:`.icons`) and ``glassNavPinned`` pins them to the bottom of the panel.
"""

from __future__ import annotations

import contextlib
from functools import partial
from typing import TYPE_CHECKING, Final, override

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QAbstractButton, QApplication, QTabWidget, QVBoxLayout, QWidget
from shiboken6 import isValid

from .icons import paint_icon
from .state import state
from .style import RADIUS, glass_colors
from .surface import paint_backdrop

if TYPE_CHECKING:
    from PySide6.QtGui import QEnterEvent, QMouseEvent, QPaintEvent, QWheelEvent

    from .chrome import GlassTitleBar

PINNED_PROPERTY: Final = 'glassNavPinned'
ICON_PROPERTY: Final = 'glassNavIcon'

# Handle: lives in the blank page padding just inside the window frame
_HANDLE_LEFT: Final = 6
_HANDLE_WIDTH: Final = 10
_HANDLE_GRIP_HEIGHT: Final = 40
# The handle starts to wake when the pointer is this close to it
_PROXIMITY_RANGE: Final = 90
# A single attention pulse the first time a dashboard opens in this session
_INTRO_DELAY_MS: Final = 700
_INTRO_MS: Final = 1600

# Panel
_PANEL_LEFT: Final = 6
_PANEL_INSET: Final = 6
_PANEL_PADDING: Final = 8
_PANEL_RADIUS: Final = 12
_PANEL_MIN_WIDTH: Final = 208
_PANEL_MAX_WIDTH: Final = 290
_ITEM_HEIGHT: Final = 38
_ITEM_SPACING: Final = 2
_ITEM_RADIUS: Final = 9
_ICON_SIZE: Final = 18
_ICON_LEFT: Final = 13
_TEXT_LEFT: Final = 42
_SHADOW: Final = 14

# Timing: a short hover intent before opening, a grace period before closing
_OPEN_DELAY_MS: Final = 110
_CLOSE_DELAY_MS: Final = 260
_POLL_MS: Final = 40
_OPEN_MS: Final = 240
_CLOSE_MS: Final = 170
_HOVER_MS: Final = 140
_HOVER_SLOP: Final = 8

# How far the content fades into the glass while the panel is out
_SCRIM_STRENGTH: Final = 0.62


def _is_pinned(tabs: QTabWidget, index: int) -> bool:
    page = tabs.widget(index)
    return page is not None and bool(page.property(PINNED_PROPERTY))


def _icon_name(tabs: QTabWidget, index: int) -> str:
    page = tabs.widget(index)
    value = page.property(ICON_PROPERTY) if page is not None else None
    return value if isinstance(value, str) else ''


def _split_tabs(tabs: QTabWidget) -> tuple[list[int], list[int]]:
    """Visible tab indices in their original order: regular first, then pinned."""
    regular: list[int] = []
    pinned: list[int] = []
    for index in range(tabs.count()):
        if tabs.isTabVisible(index):
            (pinned if _is_pinned(tabs, index) else regular).append(index)
    return regular, pinned


def _alpha(color: QColor, alpha: float) -> QColor:
    result = QColor(color)
    result.setAlphaF(max(0.0, min(1.0, alpha)))
    return result


def _mix(first: QColor, second: QColor, amount: float) -> QColor:
    amount = max(0.0, min(1.0, amount))
    return QColor.fromRgbF(
        first.redF() + (second.redF() - first.redF()) * amount,
        first.greenF() + (second.greenF() - first.greenF()) * amount,
        first.blueF() + (second.blueF() - first.blueF()) * amount,
        first.alphaF() + (second.alphaF() - first.alphaF()) * amount,
    )


def _relayout_tabs(tabs: QTabWidget) -> None:
    # QTabWidget has no QLayout; it reflows its pages on LayoutRequest
    QApplication.postEvent(tabs, QEvent(QEvent.Type.LayoutRequest))


def _transparent_overlay(widget: QWidget) -> None:
    widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


def _panel_opacity() -> float:
    # The wallpaper slice already hides what is underneath; over the live
    # desktop the tint has to do that job on its own
    if state.settings.backdrop == 'wallpaper':
        return max(state.settings.opacity, 0.55)
    return max(state.settings.opacity, 0.9)


class _Hover:
    """A 0..1 hover amount that eases in and out and repaints its widget."""

    def __init__(self, widget: QWidget) -> None:
        self.value = 0.0
        self._widget = widget
        self._animation = QVariantAnimation(widget)
        self._animation.setDuration(_HOVER_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._set)

    def _set(self, value: object) -> None:
        self.value = float(value) if isinstance(value, int | float) else 0.0
        if isValid(self._widget):
            self._widget.update()

    def to(self, target: float) -> None:
        self._animation.stop()
        self._animation.setStartValue(self.value)
        self._animation.setEndValue(target)
        self._animation.start()


class _Handle(QWidget):
    """The collapsed state: an edge light and a grip with a chevron.

    Its strength blends three signals: the pointer approaching the left edge,
    hovering the grip itself, and a one-time pulse when the window first opens.
    """

    def __init__(self, nav: GlassSidebar, parent: QWidget) -> None:
        super().__init__(parent)
        self._nav = nav
        self._hover = _Hover(self)
        self._proximity = 0.0
        self._intro = 0.0
        self.setObjectName('GlassNavHandle')
        _transparent_overlay(self)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_proximity(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        if abs(value - self._proximity) > 0.01:
            self._proximity = value
            self.update()

    def set_intro(self, value: object) -> None:
        self._intro = float(value) if isinstance(value, int | float) else 0.0
        self.update()

    @override
    def enterEvent(self, event: QEnterEvent) -> None:
        self._hover.to(1.0)
        self._nav.handle_entered()
        super().enterEvent(event)

    @override
    def leaveEvent(self, event: QEvent) -> None:
        self._hover.to(0.0)
        self._nav.handle_left()
        super().leaveEvent(event)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._nav.toggle()
            event.accept()
            return
        super().mousePressEvent(event)

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        # Scrolling over the handle steps through the tabs
        if delta := event.angleDelta().y():
            self._nav.step(-1 if delta > 0 else 1)
        event.accept()

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        colors = glass_colors()
        hover = self._hover.value
        # How awake the handle is: idle 0, near the edge ~0.6, hovered 1
        level = max(hover, 0.6 * self._proximity, 0.75 * self._intro)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center_x = self.width() / 2
        center_y = self.height() / 2

        # Edge light: a hairline down the left edge that fades out at both ends
        light = QLinearGradient(0, 0, 0, self.height())
        peak = _alpha(colors.accent, 0.16 + 0.44 * level)
        light.setColorAt(0.0, _alpha(colors.accent, 0.0))
        light.setColorAt(0.3, _alpha(colors.accent, peak.alphaF() * 0.35))
        light.setColorAt(0.5, peak)
        light.setColorAt(0.7, _alpha(colors.accent, peak.alphaF() * 0.35))
        light.setColorAt(1.0, _alpha(colors.accent, 0.0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(light)
        line_width = 2.0 + level
        painter.drawRoundedRect(
            QRectF(center_x - line_width / 2, 0, line_width, self.height()),
            line_width / 2,
            line_width / 2,
        )

        # The grip: a soft halo, then the pill itself
        grip_height = _HANDLE_GRIP_HEIGHT + 14 * level
        grip_width = 8.0 + 2 * level
        grip = QRectF(
            center_x - grip_width / 2, center_y - grip_height / 2, grip_width, grip_height
        )
        if level > 0:
            for spread, strength in ((5.0, 0.10), (2.5, 0.16)):
                halo = grip.adjusted(-spread, -spread, spread, spread)
                painter.setBrush(_alpha(colors.accent, strength * level))
                painter.drawRoundedRect(halo, halo.width() / 2, halo.width() / 2)
        idle_fill = _mix(_alpha(colors.ink, 0.12), _alpha(colors.accent, 0.22), 0.4)
        fill = _mix(idle_fill, _alpha(colors.accent, 0.42), level)
        border = _mix(_alpha(colors.ink, 0.22), _alpha(colors.accent, 0.75), level)
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(fill)
        painter.drawRoundedRect(grip, grip_width / 2, grip_width / 2)

        pen = QPen(_mix(_alpha(colors.text, 0.8), colors.text, level), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        nudge = 0.9 * level
        chevron = QPainterPath()
        chevron.moveTo(center_x - 1.4 + nudge, center_y - 3.5)
        chevron.lineTo(center_x + 1.6 + nudge, center_y)
        chevron.lineTo(center_x - 1.4 + nudge, center_y + 3.5)
        painter.drawPath(chevron)
        painter.end()


class _NavItem(QAbstractButton):
    """One destination in the panel: icon, label and an accent marker when current."""

    def __init__(self, text: str, icon: str, parent: QWidget) -> None:
        super().__init__(parent)
        self._icon = icon
        self._hover = _Hover(self)
        self.setText(text)
        self.setObjectName('GlassNavItem')
        self.setCheckable(True)
        self.setFixedHeight(_ITEM_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        label = QFont(self.font())
        label.setPointSizeF(label.pointSizeF() + 0.5)
        label.setWeight(QFont.Weight.Medium)
        self.setFont(label)

    def preferred_width(self) -> int:
        bold = QFont(self.font())
        bold.setWeight(QFont.Weight.DemiBold)
        return _TEXT_LEFT + QFontMetrics(bold).horizontalAdvance(self.text()) + 18

    @override
    def sizeHint(self) -> QSize:
        return QSize(self.preferred_width(), _ITEM_HEIGHT)

    @override
    def enterEvent(self, event: QEnterEvent) -> None:
        if self.isEnabled():
            self._hover.to(1.0)
        super().enterEvent(event)

    @override
    def leaveEvent(self, event: QEvent) -> None:
        self._hover.to(0.0)
        super().leaveEvent(event)

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        colors = glass_colors()
        hover = self._hover.value
        current = self.isChecked()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.38)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        if current:
            painter.setPen(QPen(_alpha(colors.accent, 0.34 + 0.12 * hover), 1.0))
            painter.setBrush(_alpha(colors.accent, 0.17 + 0.05 * hover))
            painter.drawRoundedRect(rect, _ITEM_RADIUS, _ITEM_RADIUS)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colors.accent)
            marker = QRectF(rect.left() + 3, rect.center().y() - 8, 3, 16)
            painter.drawRoundedRect(marker, 1.5, 1.5)
            icon_color = colors.accent
            text_color = colors.text
        else:
            if hover > 0:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(_alpha(colors.ink, 0.075 * hover))
                painter.drawRoundedRect(rect, _ITEM_RADIUS, _ITEM_RADIUS)
            icon_color = _mix(_alpha(colors.text, 0.62), colors.text, hover)
            text_color = _mix(_alpha(colors.text, 0.76), colors.text, hover)

        icon_rect = QRectF(_ICON_LEFT, (self.height() - _ICON_SIZE) / 2, _ICON_SIZE, _ICON_SIZE)
        paint_icon(painter, self._icon, icon_rect, icon_color)

        font = QFont(self.font())
        if current:
            font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(text_color)
        text_rect = QRectF(_TEXT_LEFT, 0, self.width() - _TEXT_LEFT - 10, self.height())
        text = painter.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideRight, round(text_rect.width())
        )
        painter.drawText(
            text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), text
        )
        painter.end()


class _Scrim(QWidget):
    """Fades the content into the glass and casts the panel's shadow."""

    def __init__(self, nav: GlassSidebar, parent: QWidget) -> None:
        super().__init__(parent)
        self._nav = nav
        self._amount = 0.0
        self.setObjectName('GlassNavScrim')
        _transparent_overlay(self)

    def set_amount(self, value: float) -> None:
        if value != self._amount:
            self._amount = value
            self.update()

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Clicking the faded content dismisses the panel without acting on it
        self._nav.collapse()
        event.accept()

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        event.accept()

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        if self._amount <= 0:
            return
        window = self.window()
        framed = not (window.isMaximized() or window.isFullScreen())
        radius = RADIUS if framed else 0
        # Follow the window's rounded corners rather than painting past them
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(window.rect()).translated(-self.x(), -self.y()).adjusted(0.5, 0.5, -0.5, -0.5),
            radius,
            radius,
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(_SCRIM_STRENGTH * self._amount)
        paint_backdrop(painter, self, path, max(state.settings.opacity, 0.7))
        painter.setOpacity(1.0)

        # A soft shadow along the panel's open edge
        if (panel := self._nav.panel_rect()) is not None:
            card = panel.translated(-self.x(), -self.y())
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for step in range(1, _SHADOW + 1):
                fade = 1 - step / _SHADOW
                ring = QPainterPath()
                grown = card.adjusted(-step * 0.4, -step * 0.2, step, step * 0.8)
                ring.addRoundedRect(grown, _PANEL_RADIUS + step, _PANEL_RADIUS + step)
                alpha = round(30 * fade * fade * self._amount)
                painter.setPen(QPen(QColor(0, 0, 0, alpha), 1.0))
                painter.drawPath(ring)
        painter.end()


class _Panel(QWidget):
    """The expanded state: a glass card listing every destination."""

    def __init__(self, nav: GlassSidebar, parent: QWidget) -> None:
        super().__init__(parent)
        self._nav = nav
        self._items: dict[int, _NavItem] = {}
        self._first_pinned: _NavItem | None = None
        self._has_regular = False
        self.setObjectName('GlassNavPanel')
        _transparent_overlay(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(_PANEL_PADDING, _PANEL_PADDING, _PANEL_PADDING, _PANEL_PADDING)
        layout.setSpacing(_ITEM_SPACING)
        self._layout = layout

    def rebuild(self, tabs: QTabWidget) -> int:
        """Recreate the items from the current tabs; returns the panel width."""
        while (item := self._layout.takeAt(0)) is not None:
            if (widget := item.widget()) is not None:
                widget.hide()
                widget.deleteLater()
        self._items.clear()
        self._first_pinned = None
        regular, pinned = _split_tabs(tabs)
        self._has_regular = bool(regular)
        current = tabs.currentIndex()
        widest = 0
        for index in regular:
            widest = max(widest, self._add_item(tabs, index, current))
        self._layout.addStretch(1)
        for position, index in enumerate(pinned):
            widest = max(widest, self._add_item(tabs, index, current))
            if position == 0:
                self._first_pinned = self._items[index]
        width = widest + 2 * _PANEL_PADDING
        return max(_PANEL_MIN_WIDTH, min(_PANEL_MAX_WIDTH, width))

    def _add_item(self, tabs: QTabWidget, index: int, current: int) -> int:
        item = _NavItem(tabs.tabText(index), _icon_name(tabs, index), self)
        item.setChecked(index == current)
        item.setEnabled(tabs.isTabEnabled(index))
        if tooltip := tabs.tabToolTip(index):
            item.setToolTip(tooltip)
        item.clicked.connect(partial(self._nav.select, index))
        self._layout.addWidget(item)
        self._items[index] = item
        return item.preferred_width()

    def set_current(self, current: int) -> None:
        for index, item in self._items.items():
            item.setChecked(index == current)

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        colors = glass_colors()
        ink = colors.ink
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, _PANEL_RADIUS, _PANEL_RADIUS)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # The same glass as the window, lifted slightly so it reads as a layer
        paint_backdrop(painter, self, path, _panel_opacity())
        painter.fillPath(path, _alpha(ink, 0.045))
        painter.setPen(QPen(_alpha(ink, 0.13), 1.0))
        painter.drawPath(path)
        highlight = QPainterPath()
        highlight.moveTo(rect.left() + _PANEL_RADIUS, rect.top())
        highlight.lineTo(rect.right() - _PANEL_RADIUS, rect.top())
        painter.setPen(QPen(_alpha(ink, 0.16), 1.0))
        painter.drawPath(highlight)
        # Separate the pinned group (Settings) from the regular destinations
        if self._first_pinned is not None and self._has_regular:
            y = self._first_pinned.geometry().top() - _PANEL_PADDING / 2 - 0.5
            inset = _PANEL_PADDING + 8
            painter.setPen(QPen(_alpha(ink, 0.10), 1.0))
            painter.drawLine(QPointF(inset, y), QPointF(self.width() - inset, y))
        painter.end()


class GlassSidebar(QObject):
    """Replaces a QTabWidget's tab bar with the handle and pop-out panel."""

    _intro_shown: bool = False

    def __init__(
        self, window: QWidget, tabs: QTabWidget, title_bar: GlassTitleBar | None = None
    ) -> None:
        super().__init__(window)
        self._window = window
        self._tabs = tabs
        self._title_bar = title_bar
        self._expanded = False
        self._armed = True
        self._progress = 0.0
        self._outside_ms = 0
        self._panel_width = _PANEL_MIN_WIDTH
        self._key_filter_installed = False
        self._tab_bar_was_visible = tabs.tabBar().isVisibleTo(tabs)
        tabs.tabBar().hide()
        _relayout_tabs(tabs)

        self._handle = _Handle(self, window)
        self._scrim = _Scrim(self, window)
        self._panel = _Panel(self, window)
        self._scrim.hide()
        self._panel.hide()

        self._open_timer = QTimer(self)
        self._open_timer.setSingleShot(True)
        self._open_timer.setInterval(_OPEN_DELAY_MS)
        self._open_timer.timeout.connect(self._open_from_hover)
        self._poll = QTimer(self)
        self._poll.setInterval(_POLL_MS)
        self._poll.timeout.connect(self._check_pointer)
        self._animation = QVariantAnimation(self)
        self._animation.valueChanged.connect(self._on_progress)
        self._animation.finished.connect(self._on_animation_finished)
        self._proximity_poll = QTimer(self)
        self._proximity_poll.setInterval(_POLL_MS)
        self._proximity_poll.timeout.connect(self._update_proximity)
        self._intro = QVariantAnimation(self)
        self._intro.setDuration(_INTRO_MS)
        self._intro.setStartValue(0.0)
        self._intro.setKeyValueAt(0.35, 1.0)
        self._intro.setEndValue(0.0)
        self._intro.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._intro.valueChanged.connect(self._handle.set_intro)
        self._intro_pending = not GlassSidebar._intro_shown

        tabs.currentChanged.connect(self._on_current_changed)
        tabs.installEventFilter(self)
        window.installEventFilter(self)
        self._panel_width = self._panel.rebuild(tabs)
        self._relayout()
        self._handle.show()
        self._handle.raise_()
        self._on_current_changed(tabs.currentIndex())
        if window.isVisible():
            self._play_intro()
            if window.underMouse():
                self._proximity_poll.start()

    # ------------------------------------------------------------ queries

    def panel_rect(self) -> QRectF | None:
        """The panel's geometry in window coordinates while it is out."""
        if not isValid(self._panel) or not self._panel.isVisible():
            return None
        return QRectF(self._panel.geometry())

    # ------------------------------------------------------------ actions

    def handle_entered(self) -> None:
        if not self._expanded and self._armed:
            self._open_timer.start()

    def handle_left(self) -> None:
        if not self._expanded:
            self._open_timer.stop()

    def toggle(self) -> None:
        self._open_timer.stop()
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def step(self, delta: int) -> None:
        """Move to the previous or next enabled tab in panel order."""
        if not isValid(self._tabs):
            return
        regular, pinned = _split_tabs(self._tabs)
        order = [index for index in (*regular, *pinned) if self._tabs.isTabEnabled(index)]
        if not order:
            return
        current = self._tabs.currentIndex()
        position = order.index(current) if current in order else -1
        target = order[max(0, min(len(order) - 1, position + delta))]
        if target != current:
            self._tabs.setCurrentIndex(target)

    def select(self, index: int, _checked: bool = False) -> None:
        if isValid(self._tabs) and self._tabs.isTabEnabled(index):
            self._tabs.setCurrentIndex(index)
            self._panel.set_current(self._tabs.currentIndex())
        self.collapse()

    def expand(self) -> None:
        if self._expanded or not isValid(self._tabs) or not self._window.isVisible():
            return
        self._expanded = True
        self._armed = True
        self._outside_ms = 0
        self._panel_width = self._panel.rebuild(self._tabs)
        self._relayout()
        self._scrim.show()
        self._panel.show()
        self._scrim.raise_()
        self._panel.raise_()
        self._set_key_filter(enabled=True)
        self._poll.start()
        self._animate(1.0, _OPEN_MS, QEasingCurve.Type.OutQuint)

    def collapse(self) -> None:
        if not self._expanded:
            return
        self._expanded = False
        self._open_timer.stop()
        self._set_key_filter(enabled=False)
        # The handle may now sit under the pointer; wait until it leaves first
        self._armed = False
        self._poll.start()
        self._animate(0.0, _CLOSE_MS, QEasingCurve.Type.InOutCubic)

    def detach(self) -> None:
        """Restore the tab bar and remove every overlay."""
        self._animation.stop()
        self._open_timer.stop()
        self._poll.stop()
        self._proximity_poll.stop()
        self._intro.stop()
        self._set_key_filter(enabled=False)
        if isValid(self._window):
            self._window.removeEventFilter(self)
        if isValid(self._tabs):
            self._tabs.removeEventFilter(self)
            with contextlib.suppress(RuntimeError, TypeError):
                self._tabs.currentChanged.disconnect(self._on_current_changed)
            self._tabs.tabBar().setVisible(self._tab_bar_was_visible)
            _relayout_tabs(self._tabs)
        for widget in (self._handle, self._scrim, self._panel):
            if isValid(widget):
                widget.hide()
                widget.deleteLater()
        self.deleteLater()

    # ------------------------------------------------------------ internals

    def _open_from_hover(self) -> None:
        if isValid(self._handle) and self._handle.underMouse():
            self.expand()

    def _set_key_filter(self, *, enabled: bool) -> None:
        app = QApplication.instance()
        if app is None or enabled == self._key_filter_installed:
            return
        if enabled:
            app.installEventFilter(self)
        else:
            app.removeEventFilter(self)
        self._key_filter_installed = enabled

    def _animate(self, target: float, duration: int, curve: QEasingCurve.Type) -> None:
        self._animation.stop()
        distance = abs(target - self._progress)
        if distance <= 0:
            self._on_progress(target)
            self._on_animation_finished()
            return
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(target)
        self._animation.setDuration(max(1, round(duration * distance)))
        self._animation.setEasingCurve(curve)
        self._animation.start()

    def _on_progress(self, value: object) -> None:
        progress = float(value) if isinstance(value, int | float) else 0.0
        self._progress = progress
        if not isValid(self._panel):
            return
        hidden_x = -(self._panel.width() + _SHADOW)
        x = round(hidden_x + (_PANEL_LEFT - hidden_x) * progress)
        self._panel.move(x, self._panel.y())
        self._scrim.set_amount(progress)

    def _on_animation_finished(self) -> None:
        if self._progress <= 0 and not self._expanded:
            self._scrim.hide()
            self._panel.hide()

    def _check_pointer(self) -> None:
        if not isValid(self._window):
            self._poll.stop()
            return
        position = self._window.mapFromGlobal(QCursor.pos())
        if not self._expanded:
            # Collapsed: re-arm hover once the pointer has left the handle
            if not self._handle.geometry().contains(position):
                self._armed = True
                self._poll.stop()
            return
        if not self._window.isVisible():
            self.collapse()
            return
        if QApplication.activePopupWidget() is not None:
            # A menu opened from the panel should not count as leaving it
            self._outside_ms = 0
            return
        zone = (
            self._panel.geometry()
            .united(self._handle.geometry())
            .adjusted(-_HOVER_SLOP, -_HOVER_SLOP, _HOVER_SLOP, _HOVER_SLOP)
        )
        if zone.contains(position):
            self._outside_ms = 0
            return
        self._outside_ms += _POLL_MS
        if self._outside_ms >= _CLOSE_DELAY_MS:
            self.collapse()

    def _relayout(self) -> None:
        if not isValid(self._tabs) or not isValid(self._window):
            return
        area = self._tabs.geometry()
        height = max(0, area.height() - 2 * _PANEL_INSET)
        top = area.top() + _PANEL_INSET
        self._handle.setGeometry(_HANDLE_LEFT, top, _HANDLE_WIDTH, height)
        title_bottom = 0
        if self._title_bar is not None and isValid(self._title_bar) and self._title_bar.isVisible():
            title_bottom = self._title_bar.geometry().bottom() + 1
        self._scrim.setGeometry(
            0, title_bottom, self._window.width(), self._window.height() - title_bottom
        )
        self._panel.setGeometry(self._panel.x(), top, self._panel_width, height)
        self._on_progress(self._progress)

    def _on_current_changed(self, index: int) -> None:
        if isValid(self._panel):
            self._panel.set_current(index)
        if self._title_bar is not None and isValid(self._title_bar) and isValid(self._tabs):
            self._title_bar.set_subtitle(self._tabs.tabText(index) if index >= 0 else '')

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        kind = event.type()
        # Escape closes the panel instead of the dashboard
        if self._expanded and self._is_window_escape(watched, event):
            event.accept()
            if kind == QEvent.Type.KeyPress:
                self.collapse()
            return True
        if watched is self._tabs:
            if kind in {QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show}:
                self._relayout()
        elif watched is self._window:
            if kind == QEvent.Type.Resize:
                self._relayout()
            elif kind == QEvent.Type.Show:
                self._play_intro()
            elif kind == QEvent.Type.Enter:
                self._proximity_poll.start()
            elif kind in {QEvent.Type.Leave, QEvent.Type.Hide}:
                self._proximity_poll.stop()
                self._handle.set_proximity(0.0)
            if kind in {QEvent.Type.Hide, QEvent.Type.WindowStateChange} and self._expanded:
                self.collapse()
        return False

    def _play_intro(self) -> None:
        if not self._intro_pending:
            return
        self._intro_pending = False
        GlassSidebar._intro_shown = True
        QTimer.singleShot(_INTRO_DELAY_MS, self._start_intro)

    def _start_intro(self) -> None:
        if isValid(self._handle) and not self._expanded and self._window.isVisible():
            self._intro.start()

    def _update_proximity(self) -> None:
        if not isValid(self._window) or not isValid(self._handle):
            self._proximity_poll.stop()
            return
        if self._expanded:
            self._handle.set_proximity(0.0)
            return
        position = self._window.mapFromGlobal(QCursor.pos())
        handle = self._handle.geometry()
        inside_rows = handle.top() <= position.y() <= handle.bottom()
        distance = position.x() - handle.right()
        if not inside_rows or distance > _PROXIMITY_RANGE:
            self._handle.set_proximity(0.0)
            return
        # Ease in: barely there at the edge of the range, strong next to the handle
        closeness = 1 - max(0, distance) / _PROXIMITY_RANGE
        self._handle.set_proximity(closeness * closeness)

    def _is_window_escape(self, watched: QObject, event: QEvent) -> bool:
        return (
            isinstance(event, QKeyEvent)
            and event.type() in {QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress}
            and event.key() == Qt.Key.Key_Escape
            and isinstance(watched, QWidget)
            and watched.window() is self._window
        )
