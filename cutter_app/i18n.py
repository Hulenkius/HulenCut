"""Runtime internationalization support.

Translations use the original UI text as a stable key.  This keeps the
application source readable and makes it possible to ship new locales without
changing widget code.  Language changes are applied to already-created widgets
as well as to dialogs opened later.
"""

from __future__ import annotations

import json
from pathlib import Path

from PyQt5.QtCore import QEvent, QLocale, QObject, QSettings, QTimer
from PyQt5.QtWidgets import (
    QAbstractButton,
    QAction,
    QComboBox,
    QDialogButtonBox,
    QDockWidget,
    QLabel,
    QLineEdit,
    QMenu,
    QTabWidget,
    QWidget,
)

from .utils import resource_path

DEFAULT_LANGUAGE = "zh_TW"
AVAILABLE_LANGUAGES = (
    ("zh_TW", "繁體中文"),
    ("zh_CN", "简体中文"),
    ("en_US", "English"),
)

_LANGUAGE_SETTING_KEY = "ui/language"


class TranslationManager(QObject):
    """Load translations and apply them to a live Qt object tree."""

    def __init__(self):
        super().__init__()
        self._language = DEFAULT_LANGUAGE
        self._messages: dict[str, str] = {}
        self._reverse_messages: dict[str, str] = {}
        self._old_reverse_messages: dict[str, str] = {}
        self._app = None
        self._initialized = False

    @property
    def language(self) -> str:
        return self._language

    def initialize(self, app) -> None:
        self._app = app
        if self._initialized:
            return
        setting = QSettings().value(_LANGUAGE_SETTING_KEY, self._system_language())
        self.set_language(str(setting), persist=False)
        app.installEventFilter(self)
        self._initialized = True

    def _system_language(self) -> str:
        name = QLocale.system().name().lower()
        return "en_US" if name.startswith("en") else DEFAULT_LANGUAGE

    def _load_messages(self, language: str) -> dict[str, str]:
        path = Path(resource_path(f"cutter_app/locales/{language}.json"))
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        messages = data.get("messages", data)
        return {str(key): str(value) for key, value in messages.items()}

    def set_language(self, language: str, persist: bool = True) -> None:
        if language not in dict(AVAILABLE_LANGUAGES):
            language = DEFAULT_LANGUAGE
        self._language = language
        self._old_reverse_messages = dict(self._reverse_messages)
        self._messages = self._load_messages(language)
        self._reverse_messages = {value: key for key, value in self._messages.items()}
        if persist:
            QSettings().setValue(_LANGUAGE_SETTING_KEY, language)

    def translate(self, source: str) -> str:
        """Translate a stable source string to the active language."""
        return self._messages.get(source, source)

    def to_source(self, text: str) -> str:
        """Map a translated label back to its internal, language-neutral key."""
        return self._reverse_messages.get(text, text)

    def retranslate_application(self) -> None:
        if self._app is None:
            return
        for widget in self._app.topLevelWidgets():
            self.retranslate_widget(widget)

    def retranslate_widget(self, root: QWidget) -> None:
        """Translate text-bearing children of *root* in place."""
        if root is None:
            return
        self._retranslate_object(root)
        for child in root.findChildren(QWidget):
            self._retranslate_object(child)
        for action in root.findChildren(QAction):
            self._translate_action(action)
        for menu in root.findChildren(QMenu):
            self._retranslate_menu(menu)

    def _translate_text(self, text: str) -> str:
        source = self._reverse_messages.get(text)
        if source is None:
            source = self._old_reverse_messages.get(text, text)
        return self._messages.get(source, source)

    def _retranslate_object(self, obj: QWidget) -> None:
        if isinstance(obj, QLabel):
            obj.setText(self._translate_text(obj.text()))
        elif isinstance(obj, QLineEdit):
            placeholder = obj.placeholderText()
            if placeholder:
                obj.setPlaceholderText(self._translate_text(placeholder))
        elif isinstance(obj, QAbstractButton):
            obj.setText(self._translate_text(obj.text()))
        elif isinstance(obj, QMenu):
            obj.setTitle(self._translate_text(obj.title()))
        elif isinstance(obj, QDockWidget):
            obj.setWindowTitle(self._translate_text(obj.windowTitle()))
        elif obj.windowTitle():
            obj.setWindowTitle(self._translate_text(obj.windowTitle()))

        # Keep lists of choices translated without touching user data such as
        # slice names or script names.
        if isinstance(obj, QComboBox):
            current_index = obj.currentIndex()
            for index in range(obj.count()):
                text = obj.itemText(index)
                translated = self._translate_text(text)
                if translated != text:
                    obj.setItemText(index, translated)
            obj.setCurrentIndex(current_index)

        if isinstance(obj, QTabWidget):
            for index in range(obj.count()):
                obj.setTabText(index, self._translate_text(obj.tabText(index)))

        if isinstance(obj, QDialogButtonBox):
            self._translate_dialog_buttons(obj)

        # Tooltips are set explicitly on several compact controls, so they do
        # not follow the translated label automatically.  Translate them here
        # as part of the same live language switch.
        tooltip = obj.toolTip()
        if tooltip:
            translated_tooltip = self._translate_text(tooltip)
            if translated_tooltip != tooltip:
                obj.setToolTip(translated_tooltip)

        status_tip = obj.statusTip()
        if status_tip:
            translated_status = self._translate_text(status_tip)
            if translated_status != status_tip:
                obj.setStatusTip(translated_status)

    def _translate_action(self, action: QAction) -> None:
        if action.menu() is not None:
            return
        text = action.text()
        translated = self._translate_text(text)
        if translated != text:
            action.setText(translated)

        tooltip = action.toolTip()
        if tooltip:
            translated_tooltip = self._translate_text(tooltip)
            if translated_tooltip != tooltip:
                action.setToolTip(translated_tooltip)

        status_tip = action.statusTip()
        if status_tip:
            translated_status = self._translate_text(status_tip)
            if translated_status != status_tip:
                action.setStatusTip(translated_status)

    def _retranslate_menu(self, menu: QMenu) -> None:
        menu.setTitle(self._translate_text(menu.title()))
        for action in menu.actions():
            self._translate_action(action)

    def _translate_dialog_buttons(self, box: QDialogButtonBox) -> None:
        for button in box.buttons():
            role = box.buttonRole(button)
            if role in (QDialogButtonBox.AcceptRole, QDialogButtonBox.YesRole):
                button.setText(self.translate("確定"))
            elif role in (QDialogButtonBox.RejectRole, QDialogButtonBox.NoRole):
                button.setText(self.translate("取消"))

    def eventFilter(self, obj, event):
        # Translate dialogs that are constructed after the last language
        # switch, including native-looking Qt dialogs and message boxes.
        if event.type() == QEvent.Show and isinstance(obj, QWidget):
            QTimer.singleShot(0, lambda widget=obj: self.retranslate_widget(widget))
        return super().eventFilter(obj, event)


i18n = TranslationManager()


def tr(source: str) -> str:
    """Module-level shorthand used by UI modules."""
    return i18n.translate(source)

