"""Shared appearance choices. Glass is the only style; these tune it."""

from __future__ import annotations

from typing import Final, Literal

type ColorMode = Literal['Dark', 'Light', 'System']

COLOR_MODES: Final[tuple[ColorMode, ...]] = ('Dark', 'Light', 'System')
DEFAULT_ACCENT: Final = 'Ice'
ACCENTS: Final[dict[str, str]] = {
    'Ice': '#8ab4ff',
    'Signal': '#ff5a68',
    'Mint': '#4fe0a6',
    'Amber': '#ffbe45',
    'Violet': '#b49cff',
    'Rose': '#f59ac2',
    'Coral': '#ff977a',
    'Teal': '#54d2d2',
    'Mono': '#f2f4f8',
}


def color_mode(value: object) -> ColorMode:
    if value == 'Dark':
        return 'Dark'
    if value == 'Light':
        return 'Light'
    return 'System'


def accent_name(value: object) -> str:
    return value if isinstance(value, str) and value in ACCENTS else DEFAULT_ACCENT
