"""Shared test helpers for the Glass-only appearance.

Glass is Fleasion's only theme, so tests that check how Glass restores widgets
when it is torn down switch it off explicitly and install a plain palette.
"""

from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from fleasion.gui import glass
from fleasion.gui.theme import ThemeManager


def leave_glass(mode: str = 'Light') -> None:
    """Tear Glass down and leave an opaque palette in the requested color mode."""
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    glass.theme.disable(app)
    if mode == 'Dark':
        palette = ThemeManager._dark_palette()  # pyright: ignore[reportPrivateUsage]
    elif mode == 'Light':
        palette = ThemeManager._light_palette()  # pyright: ignore[reportPrivateUsage]
    else:
        palette = QPalette(app.style().standardPalette())
    # Not an OS palette change: System mode would otherwise re-apply Glass
    ThemeManager._applying = True  # pyright: ignore[reportPrivateUsage]
    try:
        app.setPalette(palette)
    finally:
        ThemeManager._applying = False  # pyright: ignore[reportPrivateUsage]
    ThemeManager.events().changed.emit()
