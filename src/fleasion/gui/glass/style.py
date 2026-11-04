"""Glass palette, stylesheet and the SVG glyphs the stylesheet uses."""

from __future__ import annotations

from dataclasses import dataclass
from string import Template
from typing import TYPE_CHECKING, Final

from PySide6.QtGui import QColor, QPalette

from fleasion.appearance.colors import accent_color, apply_accent, on_accent
from fleasion.utils.paths import CONFIG_DIR
from fleasion.widgets.spacing import CONTROL_HEIGHT, CONTROL_PADDING

from .state import state

if TYPE_CHECKING:
    from pathlib import Path

    from .state import GlassSettings

TEXT: Final = '#f5f7fb'
MUTED: Final = 'rgba(245,247,251,0.62)'
RADIUS: Final = 14
ICON_DIR: Final[Path] = CONFIG_DIR / 'glass'


@dataclass(frozen=True)
class GlassColors:
    text: QColor
    ink: QColor
    surface: QColor
    well: QColor
    popup: QColor
    accent: QColor
    accent_text: QColor


def glass_colors(settings: GlassSettings | None = None) -> GlassColors:
    settings = settings or state.settings
    native = state.base_palette
    dark = state.dark
    surface = QColor('#101118' if dark else '#f4f5f8')
    text = QColor(TEXT if dark else '#20232b')
    well = QColor('#08090e' if dark else '#ffffff')
    popup = QColor('#1c1d26' if dark else '#f7f8fb')
    if native is not None:
        surface = native.window().color()
        text = native.windowText().color()
        well = native.base().color()
        popup = QColor(well)
    accent = accent_color(settings.accent, surface)
    return GlassColors(
        text,
        QColor('#ffffff' if dark else '#1b2030'),
        surface,
        well,
        popup,
        accent,
        on_accent(accent),
    )


_STROKE: Final = 'fill="none" stroke-linecap="round" stroke-linejoin="round"'
_ICONS: Final[dict[str, str]] = {
    'chevron-down': f'<path d="M4 6l4 4 4-4" {_STROKE} stroke="{TEXT}" stroke-width="1.8"/>',
    'chevron-up': f'<path d="M4 10l4-4 4 4" {_STROKE} stroke="{TEXT}" stroke-width="1.8"/>',
    'chevron-right': f'<path d="M6 4l4 4-4 4" {_STROKE} stroke="{TEXT}" stroke-width="1.8"/>',
    'check': f'<path d="M3.5 8.5l3 3 6-7" {_STROKE} stroke="#0c0d12" stroke-width="2.2"/>',
    'dot': '<circle cx="8" cy="8" r="3.2" fill="#0c0d12"/>',
    'win-min': f'<path d="M4.5 8h7" {_STROKE} stroke="{TEXT}" stroke-width="1.6"/>',
    'win-max': f'<rect x="4.5" y="4.5" width="7" height="7" rx="1.6" {_STROKE} '
    f'stroke="{TEXT}" stroke-width="1.5"/>',
    'win-close': f'<path d="M5 5l6 6M11 5l-6 6" {_STROKE} stroke="{TEXT}" stroke-width="1.6"/>',
}


def icon_path(name: str) -> str:
    """Return the file for a glyph; QSS can only load images from files."""
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    colors = glass_colors()
    foreground = colors.accent_text if name in {'check', 'dot'} else colors.text
    path = ICON_DIR / f'{name}-{foreground.name()[1:]}.svg'
    glyph = _ICONS[name].replace(TEXT, foreground.name()).replace('#0c0d12', foreground.name())
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
        f'{glyph}</svg>'
    )
    if not path.is_file() or path.read_text(encoding='utf-8') != svg:
        path.write_text(svg, encoding='utf-8')
    return path.as_posix()


def _rgb(hex_color: str) -> str:
    color = QColor(hex_color)
    return f'{color.red()},{color.green()},{color.blue()}'


def palette(settings: GlassSettings, *, base_palette: QPalette | None = None) -> QPalette:
    colors = glass_colors(settings)
    base = base_palette if base_palette is not None else state.base_palette
    pal = QPalette(base) if base is not None else QPalette()
    role = QPalette.ColorRole
    for color_role in (role.WindowText, role.Text, role.ButtonText, role.ToolTipText):
        foreground = (
            state.base_palette.color(color_role) if state.base_palette is not None else colors.text
        )
        pal.setColor(color_role, foreground)
        disabled = QColor(foreground)
        disabled.setAlpha(100)
        pal.setColor(QPalette.ColorGroup.Disabled, color_role, disabled)
    pal.setColor(role.Window, colors.surface)
    pal.setColor(role.Base, colors.well)
    pal.setColor(role.AlternateBase, colors.surface)
    pal.setColor(role.ToolTipBase, colors.popup)
    pal.setColor(role.Button, colors.surface)
    placeholder = QColor(colors.text)
    placeholder.setAlpha(128)
    pal.setColor(role.PlaceholderText, placeholder)
    pal = apply_accent(pal, settings.accent)
    # GlassWindows paints the surface; inherited widget backgrounds stay transparent
    window = QColor(colors.surface)
    window.setAlpha(0)
    pal.setColor(role.Window, window)
    return pal


# The visual language: flat, quiet surfaces in three depths. Cards sit slightly
# above the glass, inputs and lists sit slightly below it, and only the accent
# and focus rings carry colour. Edges are hairlines, never glossy gradients.
_CARD: Final = 'background: rgba($ink_rgb,0.045); border: 1px solid rgba($ink_rgb,0.085);'
_CONTROL: Final = 'background: rgba($ink_rgb,0.075); border: 1px solid rgba($ink_rgb,0.10);'
_CONTROL_HOVER: Final = 'background: rgba($ink_rgb,0.12); border-color: rgba($ink_rgb,0.16);'
_WELL: Final = 'background: rgba($well_rgb,$well_alpha); border: 1px solid rgba($ink_rgb,0.085);'

_STYLESHEET: Final = Template("""
QMainWindow, QDialog { background: transparent; }
QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget, QTabWidget > QWidget,
QSplitter, QStatusBar, QLabel { background: transparent; }
QComboBoxPrivateContainer { background: transparent; border: 0; }

QToolTip {
    background: rgba($popup_rgb,0.97); color: $tooltip_text;
    border: 1px solid rgba($ink_rgb,0.12); border-radius: 8px; padding: 6px 10px;
}

/* ---- Window chrome ---- */
#GlassTitleBar { background: transparent; }
#GlassTitle { font-weight: 600; font-size: 10pt; color: $text; }
#GlassSubtitle { color: $muted; font-size: 10pt; }
QPushButton#GlassWinBtn {
    min-width: 34px; max-width: 34px; min-height: 26px; max-height: 26px; padding: 0;
    border-radius: 7px; background: transparent; border: 1px solid transparent;
}
QPushButton#GlassWinBtn:hover { background: rgba($ink_rgb,0.10); }
QPushButton#GlassWinBtn:pressed { background: rgba($ink_rgb,0.06); }
QPushButton#GlassWinBtn[role="close"]:hover { background: #e5484d; }
QPushButton#GlassWinBtn[role="close"]:pressed { background: #c23a3f; }

/* ---- Inner tab bars (segmented) ---- */
QTabWidget::pane { border: 0; top: 0; }
QTabBar { qproperty-drawBase: 0; background: transparent; }
QTabBar::tab {
    background: transparent; border: 1px solid transparent; border-radius: 8px;
    padding: 5px 12px; margin: 0 2px 0 0; color: $muted;
}
QTabBar::tab:hover { color: $text; background: rgba($ink_rgb,0.06); }
QTabBar::tab:selected {
    color: $text; background: rgba($ink_rgb,0.10); border-color: rgba($ink_rgb,0.12);
}

/* ---- Cards ---- */
QGroupBox {
    $card border-radius: 12px; margin-top: 1.5em; padding: 0;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 6px; top: 1px; padding: 0 4px;
    color: $muted; font-weight: 600;
}
QFrame[frameShape="4"], QFrame[frameShape="5"] {
    background: rgba($ink_rgb,0.08); border: 0; min-height: 1px; max-height: 1px;
}
QFrame[frameShape="5"] { min-width: 1px; max-width: 1px; min-height: 0; max-height: 16777215px; }

QFrame#SubplaceSearchPanel { $card border-radius: 12px; }
QScrollArea#SubplaceRecentScroll, QScrollArea#SubplaceFavoritesScroll,
QScrollArea#SubplaceResultsScroll {
    background: rgba($well_rgb,$list_alpha); border: 1px solid rgba($ink_rgb,0.075);
    border-radius: 12px;
}
QFrame#SubplaceGameCard { $card border-radius: 12px; }
QFrame#SubplaceGameCard:hover {
    background: rgba($ink_rgb,0.08); border-color: rgba($ink_rgb,0.18);
}
QPushButton#SubplaceSidebarButton { padding: 4px 10px; border-radius: 8px; }
QPushButton#SubplaceSidebarButton:hover { background: rgba($ink_rgb,0.12); }
QWidget#SubplaceFooter { background: transparent; border: 0; }

/* ---- Buttons ---- */
QPushButton, QToolButton {
    color: $button_text; $control border-radius: 8px;
    padding: ${control_padding}px 10px; min-height: ${control_content_height}px;
}
QPushButton { min-width: 58px; }
QPushButton:hover, QToolButton:hover { $control_hover }
QPushButton:focus, QToolButton:focus { border-color: rgba($accent_rgb,0.90); }
QPushButton:pressed, QToolButton:pressed { background: rgba($ink_rgb,0.05); }
QPushButton:checked, QToolButton:checked {
    background: rgba($accent_rgb,0.22); border-color: rgba($accent_rgb,0.50);
}
QPushButton:checked:hover, QToolButton:checked:hover { background: rgba($accent_rgb,0.30); }
/* Dialogs make whichever button has focus the default; keep that quiet */
QPushButton:default { border-color: rgba($accent_rgb,0.38); }
QPushButton:disabled, QToolButton:disabled {
    color: rgba($ink_rgb,0.30); background: rgba($ink_rgb,0.03);
    border: 1px solid rgba($ink_rgb,0.05);
}
QPushButton[glassArrow="true"] {
    background: transparent; border: 0; padding: 0; min-width: 0; color: $muted;
}
QPushButton[glassArrow="true"]:hover { color: $text; background: rgba($ink_rgb,0.08); }
QPushButton[compact="true"] { padding: 0; min-width: 0; border-radius: 8px; }
QPushButton::menu-indicator { width: 0; image: none; }
QPushButton#ConflictBadge {
    background: rgba(255,190,69,0.13); border: 1px solid rgba(255,190,69,0.42); color: $warning;
}
QPushButton#ConflictBadge[clean="true"] {
    background: rgba(79,224,166,0.10); border: 1px solid rgba(79,224,166,0.34); color: $success;
}

QTabBar::tab:focus { border-color: rgba($accent_rgb,0.90); }
QCheckBox:focus, QRadioButton:focus { outline: 1px dotted rgba($accent_rgb,0.90); }

/* ---- Inputs ---- */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    color: $input_text; $well border-radius: 8px; padding: 4px 9px;
    selection-background-color: rgba($accent_rgb,0.45); selection-color: $text;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    padding: ${input_padding}px 9px; min-height: ${input_content_height}px;
}
QAbstractSpinBox > QLineEdit, QComboBox > QLineEdit {
    background: transparent; border: 0; border-radius: 0; padding: 0; min-height: 0;
}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover, QSpinBox:hover,
QDoubleSpinBox:hover { border-color: rgba($ink_rgb,0.16); }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid rgba($accent_rgb,0.85); }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: rgba($ink_rgb,0.32); background: rgba($ink_rgb,0.025);
}
QComboBox::drop-down {
    subcontrol-origin: padding; subcontrol-position: center right;
    width: 26px; border: 0; background: transparent;
}
QComboBox::down-arrow { image: url($chevron_down); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: rgba($popup_rgb,0.98); border: 1px solid transparent;
    border-radius: 10px; padding: 4px; outline: 0;
    selection-background-color: rgba($accent_rgb,0.30); selection-color: $text;
}
QComboBox QAbstractItemView::item { min-height: 26px; padding: 0 8px; border-radius: 6px; }
QSpinBox, QDoubleSpinBox { padding-right: 24px; }
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border; width: 20px; border: 0; background: transparent;
    border-radius: 6px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-position: top right; margin: 3px 3px 0 0;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-position: bottom right; margin: 0 3px 3px 0;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: rgba($ink_rgb,0.10);
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url($chevron_up); width: 10px; height: 10px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url($chevron_down); width: 10px; height: 10px;
}

/* ---- Lists and tables ---- */
/* The item-view effect paints the rim after clipping child backgrounds */
QAbstractItemView {
    color: $input_text;
    background: rgba($well_rgb,$list_alpha); alternate-background-color: rgba($ink_rgb,0.022);
    border: 1px solid transparent; border-radius: ${radius}px;
    selection-background-color: rgba($accent_rgb,0.22); selection-color: $text;
}
/* Preserve all four rounded outer corners; the separate QHeaderView reset
   below prevents duplicate header outlines without flattening the view */
QTreeView::item, QListView::item, QTableView::item { padding: 3px 6px; border: 0; }
QTreeView::item:hover, QListView::item:hover, QTableView::item:hover {
    background: rgba($ink_rgb,0.045);
}
QTreeView::item:selected, QListView::item:selected { background: rgba($accent_rgb,0.22); }
QTableView, QTableWidget { selection-background-color: rgba($accent_rgb,0.11); }
QTableView::item:selected { background: rgba($accent_rgb,0.11); }
/* QHeaderView inherits QAbstractItemView; reset the inherited inner rounded frame */
QHeaderView { background: transparent; border: 0; border-radius: 0; }
QHeaderView::section {
    background: rgba($ink_rgb,0.03); color: $muted; border: 0; font-weight: 600;
    border-bottom: 1px solid rgba($ink_rgb,0.08); padding: 6px 8px;
}
QHeaderView::section:hover { color: $text; }
QTableCornerButton::section { background: transparent; border: 0; }

/* ---- Toggles ---- */
QCheckBox, QRadioButton { spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px; height: 16px; $well
}
QCheckBox::indicator { border-radius: 5px; }
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: rgba($accent_rgb,0.75);
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: $accent; border: 1px solid $accent;
}
QCheckBox::indicator:checked { image: url($check); }
QRadioButton::indicator:checked { image: url($dot); }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    background: rgba($ink_rgb,0.03); border-color: rgba($ink_rgb,0.06);
}

/* ---- Command palette ---- */
#PaletteCard {
    background: rgba($popup_rgb,0.97);
    border: 1px solid rgba($ink_rgb,0.12); border-radius: 16px;
}
#PaletteCard QListWidget { background: transparent; border: 0; }
#PaletteCard QListWidget::item { padding: 8px 10px; border-radius: 9px; }
#PaletteCard QListWidget::item:selected { background: rgba($accent_rgb,0.26); color: $text; }
#PaletteCard QLineEdit { font-size: 13pt; padding: 9px 14px; border-radius: 11px; }
#PaletteHint { color: $muted; font-size: 8.5pt; }

/* ---- Scrollbars: thin, and only noticeable when used ---- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 4px; }
QScrollBar::handle {
    background: rgba($ink_rgb,0.16); border-radius: 3px; min-height: 32px; min-width: 32px;
}
QScrollBar::handle:hover { background: rgba($ink_rgb,0.30); }
QScrollBar::handle:pressed { background: rgba($ink_rgb,0.40); }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent; border: 0; width: 0; height: 0;
}

/* ---- Sliders and progress ---- */
QSlider::groove:horizontal {
    height: 4px; background: rgba($ink_rgb,0.12); border: 0; border-radius: 2px;
}
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
    background: #ffffff; border: 1px solid rgba(0,0,0,0.18);
}
QSlider::handle:horizontal:hover { border: 3px solid rgba($accent_rgb,0.55); }
QProgressBar {
    background: rgba($ink_rgb,0.10); border: 0; border-radius: 3px;
    text-align: center; height: 6px; color: transparent;
}
QProgressBar::chunk { background: $accent; border-radius: 3px; }

/* ---- Menus ---- */
QMenu {
    background: rgba($popup_rgb,0.97); border: 1px solid rgba($ink_rgb,0.12);
    border-radius: 12px; padding: 5px;
}
QMenu::item { padding: 6px 22px 6px 12px; border-radius: 7px; }
QMenu::item:selected { background: rgba($accent_rgb,0.26); }
QMenu::item:disabled { color: rgba($ink_rgb,0.32); }
QMenu::separator { height: 1px; background: rgba($ink_rgb,0.09); margin: 4px 8px; }
QMenuBar { background: transparent; }
QSplitter::handle { background: transparent; }
QSplitter::handle:hover { background: rgba($accent_rgb,0.35); }
""")


def stylesheet(settings: GlassSettings) -> str:
    colors = glass_colors(settings)
    native = state.base_palette
    values = {
        'text': colors.text.name(),
        'input_text': native.text().color().name() if native is not None else colors.text.name(),
        'button_text': native.buttonText().color().name()
        if native is not None
        else colors.text.name(),
        'tooltip_text': native.toolTipText().color().name()
        if native is not None
        else colors.text.name(),
        'muted': f'rgba({_rgb(colors.text.name())},0.60)',
        'ink_rgb': _rgb(colors.ink.name()),
        'well_rgb': _rgb(colors.well.name()),
        'well_alpha': '0.32' if state.dark else '0.55',
        'list_alpha': '0.24' if state.dark else '0.45',
        'popup_rgb': _rgb(colors.popup.name()),
        'accent_rgb': _rgb(colors.accent.name()),
        'accent': colors.accent.name(),
        'accent_text': colors.accent_text.name(),
        'warning': '#ffd98a' if state.dark else '#805500',
        'success': '#9ff5cf' if state.dark else '#16613f',
    }
    return _STYLESHEET.substitute(
        **values,
        radius=RADIUS - 2,
        control_padding=CONTROL_PADDING,
        control_content_height=CONTROL_HEIGHT - CONTROL_PADDING * 2 - 2,
        input_padding=CONTROL_PADDING - 1,
        input_content_height=CONTROL_HEIGHT - (CONTROL_PADDING - 1) * 2 - 2,
        card=Template(_CARD).substitute(values),
        control=Template(_CONTROL).substitute(values),
        control_hover=Template(_CONTROL_HOVER).substitute(values),
        well=Template(_WELL).substitute(values),
        chevron_down=icon_path('chevron-down'),
        chevron_up=icon_path('chevron-up'),
        check=icon_path('check'),
        dot=icon_path('dot'),
    )
