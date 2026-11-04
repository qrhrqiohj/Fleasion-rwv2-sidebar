"""Reusable UI gate for sections that require Fleasion's proxy."""

import contextlib

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fleasion.localization import tr

from . import glass
from .glass.style import glass_colors
from .theme import ThemeManager


class ProxyGate(QWidget):
    """Wrap a widget with a disabled overlay controlled by the proxy toggle."""

    def __init__(
        self,
        content: QWidget,
        message: str | None = None,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._content = content
        self._compact = compact
        self._dismissed_for_session = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content)

        self._overlay = QFrame(self)
        self._overlay.setObjectName(
            '_FleasionProxyDisabledOverlayCompact' if compact else '_FleasionProxyDisabledOverlay'
        )
        self._overlay.setVisible(False)
        self._overlay.raise_()

        overlay_layout = QVBoxLayout(self._overlay)
        overlay_layout.setContentsMargins(16, 12, 16, 12)

        label = QLabel(message or tr('proxy_gate.disabled_message'))
        label.setObjectName('_FleasionProxyDisabledOverlayLabel')
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setMinimumHeight(40 if compact else 80)

        button = QPushButton(tr('ui.gui.proxy_gate.dismiss'))
        button.setObjectName('_FleasionProxyDisabledOverlayDismissButton')
        button.clicked.connect(self.dismiss_for_session)
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(label)
        row.addStretch()

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(button)
        button_row.addStretch()

        overlay_layout.addStretch()
        overlay_layout.addLayout(row)
        overlay_layout.addSpacing(8)
        overlay_layout.addLayout(button_row)
        overlay_layout.addStretch()
        self._apply_style()
        with contextlib.suppress(TypeError):
            ThemeManager.events().changed.connect(self._apply_style)

    def event(self, event: QEvent) -> bool:
        if event.type() in {QEvent.Type.Resize, QEvent.Type.Show}:
            self._overlay.setGeometry(self.rect())
            self._overlay.raise_()
        return super().event(event)

    def set_proxy_enabled(self, enabled: bool) -> None:
        effective_enabled = enabled or self._dismissed_for_session
        self._content.setEnabled(effective_enabled)
        self._overlay.setVisible(not effective_enabled)
        if not effective_enabled:
            self._overlay.setGeometry(self.rect())
            self._overlay.raise_()

    def dismiss_for_session(self) -> None:
        self._dismissed_for_session = True
        self.set_proxy_enabled(True)

    def _apply_style(self) -> None:
        if glass.theme.active:
            self._apply_glass_style()
            return
        if self._compact:
            radius = 6
            label_padding = '10px 14px'
            label_width = 'min-width: 220px; max-width: 420px;'
        else:
            radius = 8
            label_padding = '18px 24px'
            label_width = 'min-width: 320px; max-width: 560px;'

        self._overlay.setStyleSheet(f"""
            QFrame#{self._overlay.objectName()} {{
                background-color: rgba(24, 24, 24, 150);
                border-radius: {radius}px;
            }}
            QLabel#_FleasionProxyDisabledOverlayLabel {{
                background-color: rgba(20, 20, 20, 210);
                color: white;
                border: 1px solid rgba(255, 255, 255, 80);
                border-radius: {radius}px;
                padding: {label_padding};
                font-weight: 600;
                {label_width}
            }}
            QPushButton#_FleasionProxyDisabledOverlayDismissButton {{
                background-color: rgba(255, 255, 255, 230);
                color: rgb(20, 20, 20);
                border: 1px solid rgba(255, 255, 255, 180);
                border-radius: {radius}px;
                padding: 6px 14px;
                font-weight: 700;
            }}
            QPushButton#_FleasionProxyDisabledOverlayDismissButton:hover {{
                background-color: rgba(255, 255, 255, 255);
            }}
        """)

    def _apply_glass_style(self) -> None:
        colors = glass_colors()
        ink = f'{colors.ink.red()},{colors.ink.green()},{colors.ink.blue()}'
        popup = f'{colors.popup.red()},{colors.popup.green()},{colors.popup.blue()}'
        surface = f'{colors.surface.red()},{colors.surface.green()},{colors.surface.blue()}'
        width = (
            'min-width: 220px; max-width: 420px;'
            if self._compact
            else 'min-width: 320px; max-width: 520px;'
        )
        padding = '10px 16px' if self._compact else '16px 22px'
        # A quiet glass card over a light veil, matching the rest of the window
        self._overlay.setStyleSheet(f"""
            QFrame#{self._overlay.objectName()} {{
                background-color: rgba({surface}, 0.35);
                border-radius: 12px;
            }}
            QLabel#_FleasionProxyDisabledOverlayLabel {{
                background-color: rgba({popup}, 0.94);
                color: {colors.text.name()};
                border: 1px solid rgba({ink}, 0.14);
                border-radius: 12px;
                padding: {padding};
                font-weight: 600;
                {width}
            }}
        """)
