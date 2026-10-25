"""Photoshop-inspired application theme and visual design tokens."""

from __future__ import annotations

from PyQt5.QtCore import QObject, QSettings
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt5.QtWidgets import QApplication, QStyleFactory

from .utils import resource_path

THEME_SETTING_KEY = "ui/theme"
DEFAULT_THEME = "dark"
AVAILABLE_THEMES = (
    ("dark", "深色"),
    ("light", "淺色"),
    ("system", "跟隨系統"),
)


def _windows_system_theme() -> str:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value else "dark"
    except Exception:
        return "light"


class ThemeManager(QObject):
    """Apply a compact, Photoshop-like Fusion theme."""

    def __init__(self):
        super().__init__()
        self._app: QApplication | None = None
        self._setting = DEFAULT_THEME
        self._resolved = DEFAULT_THEME

    @property
    def setting(self) -> str:
        return self._setting

    @property
    def resolved_theme(self) -> str:
        return self._resolved

    def initialize(self, app: QApplication) -> None:
        self._app = app
        app.setStyle(QStyleFactory.create("Fusion"))
        self._apply_font()
        setting = str(QSettings().value(THEME_SETTING_KEY, DEFAULT_THEME))
        self.set_theme(setting, persist=False)

    def set_theme(self, theme: str, persist: bool = True) -> None:
        valid_themes = {code for code, _ in AVAILABLE_THEMES}
        self._setting = theme if theme in valid_themes else DEFAULT_THEME
        self._resolved = (
            _windows_system_theme() if self._setting == "system" else self._setting
        )
        self._apply_palette()
        if self._app is not None:
            self._app.setStyleSheet(_build_stylesheet(self._resolved))
        if persist:
            QSettings().setValue(THEME_SETTING_KEY, self._setting)

    def _language_family(self) -> str:
        from .i18n import i18n

        preferred = {
            "zh_TW": ("Microsoft JhengHei", "Microsoft JhengHei UI"),
            "zh_CN": ("Microsoft YaHei", "Microsoft YaHei UI"),
            "en_US": ("Segoe UI", "Segoe UI Variable"),
        }.get(i18n.language, ("Segoe UI", "Segoe UI Variable"))
        available = set(QFontDatabase().families())
        if available:
            for family in preferred:
                if family in available:
                    return family
            return ""
        # In minimal/headless Qt environments the font database can be empty.
        # Use the platform-correct requested family and let Qt resolve it.
        return preferred[0]

    def ui_font(self, point_size: int = 9, bold: bool = False) -> QFont:
        family = self._language_family()
        font = QFont(family, point_size) if family else QFontDatabase.systemFont(QFontDatabase.GeneralFont)
        if family:
            font.setFamily(family)
        font.setPointSize(point_size)
        font.setBold(bold)
        font.setStyleStrategy(QFont.PreferAntialias)
        return font

    def refresh_font(self) -> None:
        if self._app is not None:
            self._app.setFont(self.ui_font())

    def _apply_font(self) -> None:
        self.refresh_font()

    def _apply_palette(self) -> None:
        if self._app is None:
            return
        dark = self._resolved == "dark"
        palette = QPalette()
        if dark:
            window = QColor("#1e1e1e")
            base = QColor("#2b2b2b")
            alt_base = QColor("#252525")
            text = QColor("#d8d8d8")
            muted = QColor("#929292")
            button = QColor("#333333")
            highlight = QColor("#2680eb")
        else:
            window = QColor("#ececec")
            base = QColor("#ffffff")
            alt_base = QColor("#f5f5f5")
            text = QColor("#202020")
            muted = QColor("#666666")
            button = QColor("#f7f7f7")
            highlight = QColor("#1473e6")

        palette.setColor(QPalette.Window, window)
        palette.setColor(QPalette.WindowText, text)
        palette.setColor(QPalette.Base, base)
        palette.setColor(QPalette.AlternateBase, alt_base)
        palette.setColor(QPalette.ToolTipBase, base)
        palette.setColor(QPalette.ToolTipText, text)
        palette.setColor(QPalette.Text, text)
        palette.setColor(QPalette.Button, button)
        palette.setColor(QPalette.ButtonText, text)
        palette.setColor(QPalette.BrightText, QColor("#ffffff"))
        palette.setColor(QPalette.Link, highlight)
        palette.setColor(QPalette.Highlight, highlight)
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.Disabled, QPalette.Text, muted)
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, muted)
        self._app.setPalette(palette)


def _build_stylesheet(theme: str) -> str:
    dark = theme == "dark"
    asset_dir = resource_path("cutter_app/assets").replace("\\", "/")
    colors = {
        "bg": "#1e1e1e" if dark else "#ececec",
        "surface": "#2b2b2b" if dark else "#f7f7f7",
        "surface_alt": "#252525" if dark else "#eeeeee",
        "surface_hover": "#3a3a3a" if dark else "#e2e2e2",
        "border": "#3d3d3d" if dark else "#cfcfcf",
        "border_strong": "#505050" if dark else "#bdbdbd",
        "text": "#d8d8d8" if dark else "#202020",
        "muted": "#929292" if dark else "#666666",
        "accent": "#2680eb" if dark else "#1473e6",
        "accent_hover": "#3d91ff" if dark else "#0d63cc",
        "accent_soft": "#243d5b" if dark else "#dcebff",
        "scroll": "#555555" if dark else "#b8b8b8",
        "asset_dir": asset_dir,
        "spin_up": f"{asset_dir}/spin_up_{'dark' if dark else 'light'}.png",
        "spin_down": f"{asset_dir}/spin_down_{'dark' if dark else 'light'}.png",
    }
    return """
QMainWindow, QDialog {{
    background: {bg};
    color: {text};
}}
QWidget {{
    color: {text};
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
QMainWindow::separator {{
    background: {border};
    width: 2px;
    height: 2px;
}}
QMenuBar {{
    background: {surface_alt};
    border-bottom: 1px solid {border};
    padding: 1px 4px;
    spacing: 0px;
    font-weight: 400;
}}
QMenuBar::item {{
    background: transparent;
    border-radius: 2px;
    padding: 3px 7px;
}}
QMenuBar::item:selected {{
    background: {surface_hover};
}}
QMenuBar::item:pressed {{
    background: {accent};
    color: #ffffff;
}}
QToolBar {{
    background: {surface_alt};
    border: none;
    border-bottom: 1px solid {border};
    spacing: 2px;
    padding: 2px 5px;
}}
QToolBar#navToolbar, QToolBar#zoomToolbar {{
    padding: 1px 5px;
}}
QToolBar::separator {{
    background: {border};
    width: 1px;
    margin: 3px 5px;
}}
QToolButton {{
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 2px 4px;
}}
QToolButton:hover {{
    background: {surface_hover};
    border-color: {border_strong};
}}
QToolBar#mainToolbar QToolButton {{
    min-width: 26px;
    min-height: 26px;
    padding: 3px;
}}
QToolBar#mainToolbar QToolButton:hover {{
    background: {surface_hover};
    border: 1px solid {border_strong};
}}
QToolBar#mainToolbar QToolButton:pressed {{
    background: {accent_soft};
}}
QToolButton#toolbarMenuButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 3px 8px 3px 5px;
    font-weight: 500;
}}
QToolButton#toolbarMenuButton:hover {{
    background: {surface_hover};
    border-color: {border_strong};
}}
QToolButton#toolbarMenuButton:pressed {{
    background: {accent_soft};
}}
QToolButton#toolbarMenuButton::menu-indicator {{
    subcontrol-position: right center;
    subcontrol-origin: padding;
    right: 3px;
}}
QPushButton {{
    background: {surface};
    border: 1px solid {border_strong};
    border-radius: 4px;
    padding: 2px 7px;
    min-height: 14px;
}}
QPushButton:hover {{
    background: {surface_hover};
    border-color: {accent};
}}
QPushButton:pressed {{
    background: {accent_soft};
}}
QPushButton:default {{
    background: {accent};
    border-color: {accent};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton:default:hover {{
    background: {accent_hover};
}}
QPushButton:disabled {{
    color: {muted};
    background: {surface_alt};
}}
QDockWidget {{
    color: {text};
    font-weight: 400;
}}
QDockWidget::title {{
    background: {surface_alt};
    border: none;
    border-bottom: 1px solid {border};
    padding: 3px 5px;
    margin: 0px;
    text-align: left;
    font-weight: 600;
}}
QDockWidget::close-button, QDockWidget::float-button {{
    border: none;
    border-radius: 3px;
    padding: 1px;
}}
QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
    background: {surface_hover};
}}
QListWidget, QTextEdit, QTextBrowser, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {surface};
    border: 1px solid {border};
    border-radius: 3px;
    padding: 2px 5px;
    selection-background-color: {accent};
    selection-color: #ffffff;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {accent};
}}
QComboBox {{
    padding-right: 24px;
}}
QComboBox::drop-down {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    border: none;
    border-left: 1px solid {border};
    background: {surface_hover};
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}}
QComboBox::drop-down:hover {{
    background: {surface_hover};
}}
QComboBox::down-arrow {{
    image: url("{spin_down}");
    width: 11px;
    height: 11px;
}}
QSpinBox, QDoubleSpinBox {{
    padding-right: 24px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    border: none;
    border-left: 1px solid {border};
    border-bottom: 1px solid {border};
    background: {surface_hover};
    border-top-right-radius: 3px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    border: none;
    border-left: 1px solid {border};
    background: {surface_hover};
    border-bottom-right-radius: 3px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {surface_hover};
}}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{
    background: {accent_soft};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url("{spin_up}");
    width: 11px;
    height: 11px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url("{spin_down}");
    width: 11px;
    height: 11px;
}}
QListWidget {{
    padding: 3px;
    outline: none;
}}
QListWidget::item {{
    border-radius: 3px;
    padding: 3px 5px;
    margin: 0px;
}}
QListWidget::item:hover {{
    background: {surface_hover};
}}
QListWidget::item:selected {{
    background: {accent};
    color: #ffffff;
}}
QMenu {{
    background: {surface};
    border: 1px solid {border_strong};
    border-radius: 3px;
    padding: 3px;
    font-weight: 400;
}}
QMenu::item {{
    border-radius: 3px;
    min-width: 100px;
    padding: 3px 22px 3px 7px;
}}
QMenu::item:selected {{
    background: {accent};
    color: #ffffff;
}}
QMenu::separator {{
    height: 1px;
    background: {border};
    margin: 3px 6px;
}}
QStatusBar {{
    background: {surface_alt};
    color: {muted};
    border-top: 1px solid {border};
    padding: 1px 6px;
}}
QStatusBar::item {{
    border: none;
}}
QLabel#hintLabel {{
    color: {muted};
    padding: 1px 0 3px 0;
}}
QLabel#dialogTitle {{
    font-size: 14pt;
    font-weight: 700;
    color: {text};
}}
QLabel#previewCanvas {{
    border: 1px solid {border};
    border-radius: 3px;
    background: {surface};
}}
QLabel#previewEmptyHint {{
    color: {muted};
    font-size: 11pt;
    padding: 12px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 1px;
}}
QScrollBar::handle:vertical {{
    background: {scroll};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 1px;
}}
QScrollBar::handle:horizontal {{
    background: {scroll};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QToolTip {{
    background: {surface_alt};
    color: {text};
    border: 1px solid {border_strong};
    border-radius: 3px;
    padding: 3px 5px;
}}
QDialog#commandPalette {{
    background: {bg};
}}
QListWidget#commandList {{
    border-radius: 4px;
    padding: 3px;
}}
QListWidget#sliceList {{
    padding: 2px;
}}
QListWidget#sliceList::item,
QListWidget#sliceList::item:hover,
QListWidget#sliceList::item:selected {{
    background: transparent;
    padding: 0px;
    margin: 0px;
    border: none;
}}
QListWidget#commandList {{
    outline: none;
}}
QListWidget#commandList::item,
QListWidget#commandList::item:hover,
QListWidget#commandList::item:selected,
QListWidget#commandList::item:selected:active,
QListWidget#commandList::item:selected:!active {{
    background: transparent;
}}
""".format(**colors)


theme_manager = ThemeManager()
