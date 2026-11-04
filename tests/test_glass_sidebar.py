"""Glass moves the dashboard tabs into a pop-out panel on the left edge."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QApplication, QDialog, QLabel, QTabWidget, QVBoxLayout

from fleasion.gui import glass
from fleasion.gui.glass import chrome
from fleasion.gui.glass.sidebar import GlassSidebar
from fleasion.gui.theme import ThemeManager

if TYPE_CHECKING:
    from collections.abc import Iterator

_TABS = (
    ('Replacer', 'replacer'),
    ('Scraper', 'scraper'),
    ('Modifications', 'modifications'),
    ('Subplace Joiner', 'subplace_joiner'),
    ('Miscellaneous', 'miscellaneous'),
    ('Proxy', 'proxy'),
)


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Iterator[QApplication]:
    instance = QApplication.instance()
    application = instance if isinstance(instance, QApplication) else QApplication([])
    previous_theme = str(getattr(ThemeManager, '_current_theme'))
    for name in ('_current_theme', '_effective_theme', '_system_style_name'):
        monkeypatch.setattr(ThemeManager, name, getattr(ThemeManager, name))
    ThemeManager.apply_theme('Light')
    yield application
    ThemeManager.apply_theme(previous_theme)
    application.processEvents()


def _dashboard() -> tuple[QDialog, QTabWidget]:
    window = QDialog()
    layout = QVBoxLayout(window)
    tabs = QTabWidget()
    for title, icon in _TABS:
        page = QLabel(title)
        page.setProperty(glass.NAV_ICON, icon)
        tabs.addTab(page, title)
    settings = QLabel('Settings')
    settings.setProperty(glass.NAV_ICON, 'settings')
    settings.setProperty(glass.NAV_PINNED, True)  # ruff: ignore[boolean-positional-value-in-call] - Qt API
    tabs.addTab(settings, 'Settings')
    layout.addWidget(tabs)
    window.resize(900, 700)
    glass.theme.attach(window, tabs=tabs)
    return window, tabs


def _sidebar(window: QDialog) -> GlassSidebar:
    installed = chrome._installed[window]  # pyright: ignore[reportPrivateUsage]
    assert installed.sidebar is not None
    return installed.sidebar


def _items(window: QDialog) -> list[QAbstractButton]:
    return [
        item
        for item in window.findChildren(QAbstractButton)
        if item.objectName() == 'GlassNavItem' and item.isVisible()
    ]


def test_glass_replaces_tab_bar_with_side_panel(app: QApplication) -> None:
    window, tabs = _dashboard()
    try:
        ThemeManager.apply_theme('Glass')
        window.show()
        app.processEvents()
        sidebar = _sidebar(window)
        assert not tabs.tabBar().isVisible()
        # The handle lives inside the frame; it must not widen the left margin
        layout = window.layout()
        assert layout is not None
        margins = layout.contentsMargins()
        assert margins.left() == margins.right()

        sidebar.expand()
        QTest.qWait(350)
        items = _items(window)
        assert [item.text() for item in items] == [*(title for title, _ in _TABS), 'Settings']
        # Settings is pinned to the bottom, away from the other destinations
        assert items[-1].geometry().top() - items[-2].geometry().bottom() > 3 * items[0].height()
        assert all(item.height() == items[0].height() >= 34 for item in items)
        items[-1].click()
        assert tabs.currentIndex() == len(_TABS)
        QTest.qWait(300)
        assert not _items(window)
    finally:
        ThemeManager.apply_theme('Light')
        app.processEvents()
        assert tabs.tabBar().isVisibleTo(tabs)
        window.close()
        window.deleteLater()
        app.processEvents()


def test_escape_closes_panel_before_dashboard(app: QApplication) -> None:
    window, _tabs = _dashboard()
    QShortcut(QKeySequence('Escape'), window).activated.connect(window.close)
    try:
        ThemeManager.apply_theme('Glass')
        window.show()
        window.activateWindow()
        app.processEvents()
        sidebar = _sidebar(window)
        sidebar.expand()
        QTest.qWait(50)
        QTest.keyClick(window, Qt.Key.Key_Escape)
        app.processEvents()
        assert window.isVisible()
        # Once the panel is closed, Escape behaves as before
        QTest.qWait(300)
        QTest.keyClick(window, Qt.Key.Key_Escape)
        app.processEvents()
        assert not window.isVisible()
    finally:
        ThemeManager.apply_theme('Light')
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
