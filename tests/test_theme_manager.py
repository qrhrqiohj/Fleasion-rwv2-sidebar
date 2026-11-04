import sys
import types
from collections.abc import Callable, Mapping
from typing import Protocol, cast

import pytest
from PySide6.QtGui import QColor, QPalette

from fleasion.gui import theme as theme_module
from fleasion.gui.theme import ThemeManager


class _StyleLike(Protocol):
    def objectName(self) -> str: ...
    def standardPalette(self) -> QPalette: ...


def _resolve_palette(app: object, mode: str) -> QPalette:
    callback = cast(
        'Callable[[object, str], QPalette]', getattr(ThemeManager, '_resolve_palette')
    )
    return callback(app, mode)


def _windows_system_theme(app: object) -> str:
    callback = cast('Callable[[object], str]', getattr(ThemeManager, '_windows_system_theme'))
    return callback(app)


def _theme_state(name: str) -> str:
    return cast('str', getattr(ThemeManager, name))


def _set_color_scheme_noop(_app: object, _name: str) -> None:
    return None


def _dark_system_theme(_app: object) -> str:
    return 'Dark'


def _light_system_theme(_app: object) -> str:
    return 'Light'


def _record_color_scheme(values: list[str]) -> Callable[[object, str], None]:
    def record(_app: object, color_scheme_name: str) -> None:
        values.append(color_scheme_name)

    return record


class _FakeStyle:
    def __init__(self, name: str = 'mock-style', palette: QPalette | None = None) -> None:
        self._name = name
        self._palette = palette or QPalette()

    def objectName(self) -> str:
        return self._name

    def standardPalette(self) -> QPalette:
        return self._palette


class _FakeApp:
    def __init__(self, style: _StyleLike | None = None, palette: QPalette | None = None) -> None:
        self._style = style or _FakeStyle()
        self._palette = palette or QPalette()
        self.style_name: str | None = None
        self.applied_palette: QPalette | None = None

    def style(self) -> _StyleLike:
        return self._style

    def setStyle(self, style_name: str) -> None:
        self.style_name = style_name
        self._style = _FakeStyle(style_name, self._style.standardPalette())

    def setPalette(self, palette: QPalette) -> None:
        self.applied_palette = palette
        self._palette = palette

    def palette(self) -> QPalette:
        return self._palette


def test_panel_colors_use_qpalette_before_glass_is_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fleasion.gui import glass

    monkeypatch.setattr(glass.theme, '_filter', None)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor('#123456'))
    palette.setColor(QPalette.ColorRole.Mid, QColor('#abcdef'))

    colors = ThemeManager.panel_colors(palette)

    assert colors.section_background == QColor('#123456')
    assert colors.section_border == QColor('#abcdef')
    assert colors.container_background_css == 'background-color: palette(window);'


def test_transparent_palette_does_not_replace_saved_native_palette(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    native = QPalette()
    native.setColor(QPalette.ColorRole.Window, QColor('#323232'))
    transparent = QPalette(native)
    transparent.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
    monkeypatch.setattr(ThemeManager, '_applying', False)
    monkeypatch.setattr(ThemeManager, '_system_palette', native)

    assert not ThemeManager.remember_native_palette(transparent)
    assert ThemeManager._system_palette is native  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(('mode', 'window'), [('Dark', '#323232'), ('Light', '#efefef')])
def test_forced_modes_resolve_fleasion_palettes(
    monkeypatch: pytest.MonkeyPatch, mode: str, window: str
) -> None:
    schemes: list[str] = []
    monkeypatch.setattr(ThemeManager, '_set_color_scheme', staticmethod(_record_color_scheme(schemes)))

    palette = _resolve_palette(_FakeApp(), mode)

    assert palette.color(QPalette.ColorRole.Window) == QColor(window)
    assert schemes == [mode]


@pytest.mark.parametrize(
    ('system', 'window'), [(_dark_system_theme, '#323232'), (_light_system_theme, '#efefef')]
)
def test_windows_system_mode_follows_the_os_preference(
    monkeypatch: pytest.MonkeyPatch, system: Callable[[object], str], window: str
) -> None:
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(ThemeManager, '_effective_theme', 'System')
    monkeypatch.setattr(ThemeManager, '_set_color_scheme', staticmethod(_set_color_scheme_noop))
    monkeypatch.setattr(ThemeManager, '_windows_system_theme', staticmethod(system))

    palette = _resolve_palette(_FakeApp(), 'System')

    assert palette.color(QPalette.ColorRole.Window) == QColor(window)
    assert _theme_state('_effective_theme') == system(None)


@pytest.mark.parametrize('platform', ['darwin', 'linux'])
def test_other_platforms_tint_glass_from_the_native_palette(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    native = QPalette()
    native.setColor(QPalette.ColorRole.Window, QColor('#2a3b4c'))
    monkeypatch.setattr(sys, 'platform', platform)
    monkeypatch.setattr(ThemeManager, '_system_palette', native)
    monkeypatch.setattr(ThemeManager, '_set_color_scheme', staticmethod(_set_color_scheme_noop))

    palette = _resolve_palette(_FakeApp(), 'System')

    assert palette.color(QPalette.ColorRole.Window) == QColor('#2a3b4c')
    assert palette is not native


def test_windows_system_theme_reads_apps_use_light_theme_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Key:
        def __enter__(self) -> _Key:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    values: dict[str, int] = {'AppsUseLightTheme': 0}

    def open_key(*_args: object, **_kwargs: object) -> _Key:
        return _Key()

    def query_value(_key: object, name: str) -> tuple[int, int]:
        return values[name], 4

    fake_winreg = types.SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        KEY_QUERY_VALUE=1,
        OpenKey=open_key,
        QueryValueEx=query_value,
    )
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(theme_module, 'winreg', fake_winreg, raising=False)

    assert _windows_system_theme(_FakeApp()) == 'Dark'
    values['AppsUseLightTheme'] = 1
    assert _windows_system_theme(_FakeApp()) == 'Light'
