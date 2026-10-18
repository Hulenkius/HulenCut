"""A fast keyboard-driven command palette."""

from __future__ import annotations

from PyQt5.QtCore import QEvent, QRectF, QSize, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction,
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
)

from .i18n import tr


def _fuzzy_match(query: str, text: str) -> bool:
    query = query.strip().lower()
    if not query:
        return True
    text = text.lower()
    if query in text:
        return True
    position = 0
    for character in query:
        position = text.find(character, position)
        if position < 0:
            return False
        position += 1
    return True


COMMAND_ROW_HEIGHT = 34


class _CommandItemDelegate(QStyledItemDelegate):
    """Draw selection as a slim marker instead of a full-row background.

    Painting the item ourselves makes the appearance independent of Qt's
    selected/hover state combinations and prevents language or font changes
    from reintroducing a background that overlaps adjacent text.
    """

    def sizeHint(self, option, index):
        return QSize(0, COMMAND_ROW_HEIGHT)

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect.adjusted(1, 1, -1, -1)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)

        marker_color = option.palette.highlight().color() if selected else option.palette.mid().color()
        if selected or hovered:
            marker = QRectF(rect.left() + 2, rect.top() + 3, 3, rect.height() - 6)
            painter.fillRect(marker, marker_color)

        font = QFont(option.font)
        if selected:
            font.setBold(True)
        painter.setFont(font)
        painter.setPen(option.palette.text().color())
        text = str(index.data(Qt.DisplayRole) or "")
        text_rect = rect.adjusted(12, 0, -8, 0)
        text = painter.fontMetrics().elidedText(text, Qt.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)
        painter.restore()


class CommandPaletteDialog(QDialog):
    """Searchable list of available QActions."""

    def __init__(self, actions: list[QAction], parent=None):
        super().__init__(parent)
        self.setObjectName("commandPalette")
        self.setWindowTitle(tr("命令面板"))
        self.setModal(True)
        self.resize(640, 460)
        self.result_action: QAction | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(10)

        title = QLabel(tr("快速操作"), self)
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(tr("搜索命令"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._populate)
        self.search.returnPressed.connect(self._accept_current)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)

        self.commands = QListWidget(self)
        self.commands.setObjectName("commandList")
        self.commands.setUniformItemSizes(True)
        self.commands.setSpacing(0)
        self.commands.setItemDelegate(_CommandItemDelegate(self.commands))
        self.commands.itemActivated.connect(lambda _item: self._accept_current())
        layout.addWidget(self.commands, 1)

        self._actions = self._collect_actions(actions)
        self._populate()
        self.search.setFocus()

    def _collect_actions(self, actions: list[QAction]) -> list[QAction]:
        result = []
        seen = set()
        for action in actions:
            if action.isSeparator() or not action.isEnabled() or action.menu() is not None:
                continue
            text = action.text().strip().replace("&", "")
            if not text:
                continue
            shortcut = action.shortcut().toString()
            key = (text, shortcut)
            if key in seen:
                continue
            seen.add(key)
            result.append(action)
        result.sort(key=lambda item: item.text().lower())
        return result

    def _populate(self) -> None:
        query = self.search.text()
        self.commands.clear()
        for action in self._actions:
            shortcut = action.shortcut().toString()
            searchable = f"{action.text()} {shortcut}"
            if not _fuzzy_match(query, searchable):
                continue
            label = action.text().replace("&", "")
            if shortcut:
                label = f"{label}    {shortcut}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, action)
            item.setSizeHint(QSize(0, COMMAND_ROW_HEIGHT))
            self.commands.addItem(item)
        if self.commands.count():
            self.commands.setCurrentRow(0)
        else:
            empty = QListWidgetItem(tr("沒有符合的命令"))
            empty.setFlags(Qt.NoItemFlags)
            empty.setSizeHint(QSize(0, COMMAND_ROW_HEIGHT))
            self.commands.addItem(empty)

    def _accept_current(self) -> None:
        item = self.commands.currentItem()
        if item is None:
            return
        action = item.data(Qt.UserRole)
        if isinstance(action, QAction):
            self.result_action = action
            self.accept()

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Down:
                self.commands.setFocus()
                self.commands.setCurrentRow(0)
                return True
            if event.key() == Qt.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, event)
