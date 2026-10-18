"""Main application window and feature orchestration."""
import json
import math
import os
import shutil
import urllib.request
from pathlib import Path

import numpy as np
from cv2 import (
    BORDER_CONSTANT,
    CHAIN_APPROX_SIMPLE,
    COLOR_BGRA2GRAY,
    INTER_LINEAR,
    RETR_EXTERNAL,
    THRESH_BINARY,
    THRESH_BINARY_INV,
    boundingRect,
    cvtColor,
    findContours,
    getRotationMatrix2D,
    threshold,
    warpAffine,
)
from PyQt5.QtCore import QRectF, QSettings, QSize, Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QFont, QIcon, QImage, QPixmap, QTransform
from PyQt5.QtWidgets import QAbstractSpinBox, QAction, QApplication, QComboBox, QDialog, QDockWidget, QFileDialog, QGraphicsItem, QHBoxLayout, QInputDialog, QLabel, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSpinBox, QToolButton, QVBoxLayout, QWidget

from .command_palette import CommandPaletteDialog
from .dialogs import (
    BatchRenameDialog,
    CheckUpdateDialog,
    DivideSlicesDialog,
    FilterSlicesDialog,
    JsonImportPresetDialog,
    MoveSlicesDialog,
    NormalizeSlicesDialog,
    ScaleProjectDialog,
    ScaleSlicesDialog,
    TableDetectDialog,
)
from .graphics import SliceListWidget, SliceRect, SliceView
from .icons import make_icon
from .i18n import AVAILABLE_LANGUAGES, i18n, tr
from .panels import (
    AlignDistributeWidget,
    AutoProcessPanel,
    FindWidget,
    PreviewPanel,
    SliceDimensionWidget,
    StraightenWidget,
)
from .scripting import ScriptRecorder
from .theme import AVAILABLE_THEMES, theme_manager
from .utils import resource_path


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")


class MainWindow(QMainWindow):
    settings_organization = "HulenCut"
    settings_application = "HulenCutApp"

    def __init__(self):
        super().__init__()
        QApplication.setApplicationName("HulenCut")
        self.setWindowTitle(tr("囫圇切 HulenCut v0.8.0"))
        self.currentVersion = "v0.8.0"  # 當前版本號
        self.setWindowIcon(QIcon(resource_path("hulencutter.ico")))
        self.setAcceptDrops(True)
        self.resize(1280, 800)
        self.setMinimumSize(1100, 700)
        self.fixedSliceSize = None
        self._themed_icons = []
        self._themed_menus = []
        self._themed_buttons = []
        # 定幅切片原點（可選：top_left, top, top_right, left, center, right, bottom_left, bottom, bottom_right）
        self.fixedSliceOrigin = "center"
        self.sliceView = SliceView(self)
        self.sliceView.setMinimumWidth(480)
        self.setCentralWidget(self.sliceView)
        # 導航防重入旗標，避免快捷鍵與動作同時觸發造成重入
        self._navigating = False
        self.inLoopMode = False   # 跨頁循環模式旗標（後端執行時暫停視圖刷新）
        bar = self.statusBar()  # 確保狀態欄被初始化
        
        original_showMessage = bar.showMessage
        def new_showMessage(msg, timeout=0):
            # 靜默模式下不顯示任何訊息
            if not self.inLoopMode:
                new_msg = msg.replace("\\", "/")
                original_showMessage(new_msg, timeout)
            
        bar.showMessage = new_showMessage
        self.statusBar().showMessage(tr("準備就緒"))
        # 預設導出目錄與格式
        self.defaultExportDir = ""
        self.defaultExportFormat = ""  # 若未設定則為空
        self.jsonImportPreset = None   # 看典json導入預設參數
        self.defaultProjectPath = None  # 預設工程文件路徑
        # 支援導入文件夾以及圖片導航
        self.currentFolder = ""
        self.folderImages = []  # 初始化 folderImages 屬性
        self.currentImageIndex = -1
        self.sliceList = SliceListWidget(self)
        # 在頂部添加操作按鈕
        sliceListContainer = QWidget(self)
        vLayout = QVBoxLayout(sliceListContainer)
        # 水平佈局，放置「置頂」「上移」「下移」「置底」按鈕
        btnLayout = QHBoxLayout()
        btnLayout.setSpacing(3)
        self.btnTop = QToolButton(self)
        self.btnTop.setToolTip(tr("將所選切片移到最前"))
        self.btnTop.setAutoRaise(True)
        self.btnTop.clicked.connect(self.topSlice)
        self._set_button_icon(self.btnTop, "to-top")
        self.btnUp = QToolButton(self)
        self.btnUp.setToolTip(tr("將所選切片上移一位"))
        self.btnUp.setAutoRaise(True)
        self.btnUp.clicked.connect(self.upSlice)
        self._set_button_icon(self.btnUp, "up")
        self.btnDown = QToolButton(self)
        self.btnDown.setToolTip(tr("將所選切片下移一位"))
        self.btnDown.setAutoRaise(True)
        self.btnDown.clicked.connect(self.downSlice)
        self._set_button_icon(self.btnDown, "down")
        self.btnBottom = QToolButton(self)
        self.btnBottom.setToolTip(tr("將所選切片移到最後"))
        self.btnBottom.setAutoRaise(True)
        self.btnBottom.clicked.connect(self.bottomSlice)
        self._set_button_icon(self.btnBottom, "to-bottom")
        btnLayout.addWidget(self.btnTop)
        btnLayout.addWidget(self.btnUp)
        btnLayout.addWidget(self.btnDown)
        btnLayout.addWidget(self.btnBottom)
        vLayout.addLayout(btnLayout)
        vLayout.addWidget(self.sliceList)
        btnClearNames = QPushButton(tr("清空切片名稱"), self)
        btnClearNames.setToolTip(tr("清空所有切片名稱但不刪除切片"))
        btnClearNames.clicked.connect(self.clearAllSliceNames)
        self._set_button_icon(btnClearNames, "clear-text")
        btnClear = QPushButton(tr("清空切片"), self)
        btnClear.setToolTip(tr("刪除目前圖片上的所有切片"))
        btnClear.clicked.connect(self.clearAllSlices)
        self._set_button_icon(btnClear, "trash")
        btnClearLayout = QHBoxLayout()
        btnClearLayout.addWidget(btnClearNames)
        btnClearLayout.addWidget(btnClear)
        vLayout.addLayout(btnClearLayout)
        sliceListContainer.setLayout(vLayout)
        dockList = QDockWidget(tr("切片列表"), self)
        dockList.setObjectName("dockList")
        dockList.setWidget(sliceListContainer)
        self.dockList = dockList
        self.addDockWidget(Qt.LeftDockWidgetArea, dockList)
        self.sliceList.itemClicked.connect(self.onSliceItemClicked)
        # 連結列表多選事件
        self.sliceList.itemSelectionChanged.connect(self.onSliceSelectionChanged)
        self.sliceDimWidget = SliceDimensionWidget(self)
        dockDim = QDockWidget(tr("定幅切片"), self)
        dockDim.setObjectName("dockDim")
        dockDim.setWidget(self.sliceDimWidget)
        self.dockDim = dockDim
        
        # 校正工具面板
        self.straightWidget = StraightenWidget(self)
        dockStraight = QDockWidget(tr("裁剪校正"), self)
        dockStraight.setObjectName("dockStraight")
        dockStraight.setWidget(self.straightWidget)
        self.dockStraight = dockStraight
        self.addDockWidget(Qt.LeftDockWidgetArea, dockList)        # 切片列表已存在
        self.addDockWidget(Qt.LeftDockWidgetArea, dockStraight)
        self.addDockWidget(Qt.LeftDockWidgetArea, dockDim)
        self.splitDockWidget(dockList, dockStraight, Qt.Vertical)
        self.splitDockWidget(dockStraight, dockDim, Qt.Vertical)
        # 裁剪狀態
        self.croppingMode = False
        self.cropRectItem = None

        # 自動處理面板
        self.auto_process_panel = AutoProcessPanel(self)      
        self.auto_process_panel.setObjectName("autoProcessPanel")      
        self.addDockWidget(Qt.LeftDockWidgetArea, self.auto_process_panel)      
        self.splitDockWidget(dockDim, self.auto_process_panel, Qt.Vertical)      
        self.auto_process_panel.setVisible(True)

        self.currentImagePath = None  # 儲存當前圖片完整路徑
        # 連結 scene 的 selectionChanged 信號
        self.sliceView.scene().selectionChanged.connect(self.syncListSelectionWithScene)
        self.sliceView.scene().selectionChanged.connect(self.update_preview_panel)
        self.projectEdited = False  # 工程狀態標誌
        # 用來保存上次成功保存時的工程快照（用於判斷實際是否有改動）
        self._last_saved_project_data = ""
        # 標記當前圖片是否有成功自動載入工程文件
        self._project_loaded = False
        # 在大量載入/切換圖片或工程時，抑制預覽更新以避免訪問已刪除項
        self._suppressPreviewUpdate = False
        self.dividingSlices = False      # 劃分切片模式旗標
        self.dividePoints = []           # 儲存使用者點選的兩個點
        self.divide_params = None        # 儲存劃分參數 (cols, rows, method)
        # --- 直線校正模式狀態 ---
        self.straighteningMode           = False
        self.straightenPreviewActive     = False
        self.straightenStartPoint        = None
        self.straightenEndPoint          = None
        self.tempStraightenLine          = None
        self.originalPixmapBeforeStraighten = None
        self.straightenAngle             = 0.0
        # 用於存放直線校正的兩個點
        self.straightenPoints            = []
        self.recorder = ScriptRecorder()
        self.auto_process_panel.btn_record.clicked.connect(self.toggle_recording)
        self.auto_process_panel.btn_import.clicked.connect(self.import_script)
        self.auto_process_panel.btn_run.clicked.connect(self.run_script)
        self.auto_process_panel.btn_delete.clicked.connect(self.delete_script)
        self.auto_process_panel.script_list.itemDoubleClicked.connect(lambda item: self.run_script())
        self.update_script_list()
        self.createToolBar()

        # 狀態指示器（固定在狀態列右側）
        try:
            self.modifiedIndicator = QLabel("")
            self.modifiedIndicator.setStyleSheet("padding-left:8px;")
            self.statusBar().addPermanentWidget(self.modifiedIndicator)
        except Exception:
            self.modifiedIndicator = None
        # 初始化顯示一次
        if hasattr(self, "updateModifiedIndicator"):
            self.updateModifiedIndicator()
        
        # 預覽面板
        self.previewPanel = PreviewPanel(self)
        self.previewPanel.set_slice_list(self.sliceList)
        self.previewPanel.setMinimumWidth(280)
        self.previewPanel.setMinimumHeight(240)
        self.addDockWidget(Qt.RightDockWidgetArea, self.previewPanel)
        self.previewPanel.setVisible(True)
        self.splitDockWidget(self.previewPanel, self.auto_process_panel, Qt.Vertical)
        self.previewPanel.raise_()
        
        # 對齊與分布面板
        self.alignWidget = AlignDistributeWidget(self)
        dockAlign = QDockWidget(tr("對齊與分布"), self)
        dockAlign.setObjectName("dockAlign")
        dockAlign.setWidget(self.alignWidget)
        self.dockAlign = dockAlign
        self.addDockWidget(Qt.RightDockWidgetArea, dockAlign)
        # 讓它與預覽面板垂直排列
        self.splitDockWidget(self.previewPanel, dockAlign, Qt.Vertical)
        # 每次切片在視圖中選擇改變時更新按鈕狀態
        self.sliceView.scene().selectionChanged.connect(self.alignWidget.update_buttons_state)
        # 新增：每次切片在列表中選擇改變時也更新按鈕狀態
        self.sliceList.itemSelectionChanged.connect(self.alignWidget.update_buttons_state)
        # 初始按鈕狀態
        self.alignWidget.update_buttons_state()

        # 査找切片面板（預設關閉，但支持記憶位置）
        self.findWidget = FindWidget(self)
        dockFind = QDockWidget(tr("査找切片"), self)
        dockFind.setObjectName("dockFind")
        dockFind.setWidget(self.findWidget)
        self.dockFind = dockFind
        dockFind.setVisible(False)  # 默認關閉
        self.addDockWidget(Qt.LeftDockWidgetArea, dockFind)

        self.loadLayout()
        self._ensureToolbarVisibility()
        
        # 切片列表選擇變更時更新預覽
        self.sliceList.itemSelectionChanged.connect(self.update_preview_panel)
        # 名稱輸入框內容變更時即時同步
        self.previewPanel.nameEdit.textEdited.connect(self.previewPanel.apply_name)
        self.previewPanel.update_preview(None)
        self._refresh_ui_fonts()
        QTimer.singleShot(0, self._ensureComfortableLayout)
        
    def _refresh_ui_fonts(self) -> None:
        font = theme_manager.ui_font()
        widgets = [self, *self.findChildren(QWidget)]
        for widget in widgets:
            current = widget.font()
            updated = QFont(font)
            if current.pointSize() > 0:
                updated.setPointSize(current.pointSize())
            updated.setBold(current.bold())
            updated.setItalic(current.italic())
            updated.setUnderline(current.underline())
            widget.setFont(updated)
        if hasattr(self, "sliceView"):
            self.sliceView.viewport().update()

    def changeLanguage(self, language: str) -> None:
        """Switch UI language and update all currently visible widgets."""
        i18n.set_language(language)
        theme_manager.refresh_font()
        self._refresh_ui_fonts()
        i18n.retranslate_application()
        for code, action in getattr(self, "languageActions", {}).items():
            action.setChecked(code == language)
        if hasattr(self, "updateModifiedIndicator"):
            self.updateModifiedIndicator()
        if hasattr(self, "update_preview_panel"):
            self.update_preview_panel()

    def _ensureComfortableLayout(self, force: bool = False) -> None:
        """Give the canvas and preview priority over peripheral panels."""
        if not hasattr(self, "dockList") or not hasattr(self, "previewPanel"):
            return
        central_width = self.centralWidget().width()
        preview_height = self.previewPanel.height()
        if not force and central_width >= 520 and preview_height >= 260:
            return

        left_docks = [self.dockList, self.dockStraight, self.dockDim, self.auto_process_panel]
        right_docks = [self.previewPanel, self.dockAlign]
        self.resizeDocks(left_docks, [290, 290, 290, 300], Qt.Horizontal)
        self.resizeDocks(right_docks, [320, 320], Qt.Horizontal)
        self.resizeDocks(left_docks, [300, 105, 135, 300], Qt.Vertical)
        self.resizeDocks(right_docks, [500, 120], Qt.Vertical)

    def _ensureToolbarVisibility(self) -> None:
        if hasattr(self, "navToolbar"):
            self.addToolBar(Qt.TopToolBarArea, self.navToolbar)
            self.navToolbar.setVisible(True)
        if hasattr(self, "actToggleNavToolbar"):
            self.actToggleNavToolbar.setChecked(True)

    def resetDockLayout(self) -> None:
        self._ensureToolbarVisibility()
        self.dockList.setVisible(True)
        self.dockDim.setVisible(True)
        self.dockStraight.setVisible(True)
        self.auto_process_panel.setVisible(True)
        self.previewPanel.setVisible(True)
        self.dockAlign.setVisible(False)
        self.dockFind.setVisible(False)
        self.actToggleSliceList.setChecked(True)
        self.actToggleDimension.setChecked(True)
        self.actToggleStraighten.setChecked(True)
        self.actToggleAutoProcess.setChecked(True)
        self.actTogglePreviewPanel.setChecked(True)
        self.actToggleAlign.setChecked(False)
        self.actToggleFind.setChecked(False)
        QTimer.singleShot(0, lambda: self._ensureComfortableLayout(force=True))

    def showCommandPalette(self) -> None:
        dialog = CommandPaletteDialog(self.findChildren(QAction), self)
        if dialog.exec_() == QDialog.Accepted and dialog.result_action is not None:
            QTimer.singleShot(0, dialog.result_action.trigger)

    def changeTheme(self, theme: str) -> None:
        theme_manager.set_theme(theme)
        self._refresh_icons()
        for code, action in getattr(self, "themeActions", {}).items():
            action.setChecked(code == theme)
        self.sliceView.viewport().update()

    @staticmethod
    def _has_local_urls(event) -> bool:
        mime = event.mimeData()
        return bool(mime and mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()))

    def dragEnterEvent(self, event):
        if self._has_local_urls(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._has_local_urls(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if self._has_local_urls(event):
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            self.handleDroppedPaths(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def handleDroppedPaths(self, paths: list[str]) -> None:
        for path in paths:
            if os.path.isdir(path):
                self.loadFolderPath(path)
                return
            suffix = Path(path).suffix.lower()
            if suffix == ".cutter":
                self.openProjectPath(path)
                return
            if suffix in IMAGE_EXTENSIONS:
                self.loadImagePath(path)
                return
            if suffix == ".json" and self.currentImagePath:
                self.importKandianJson(path)
                return
        self.statusBar().showMessage(tr("不支援此檔案類型"))

    def eventFilter(self, obj, event):
        if obj == self.imageJumpSpin and event.type() == event.KeyPress:
            if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Left:
                self.prevImage()
                return True
            elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Right:
                self.nextImage()
                return True
        return super().eventFilter(obj, event)
        
    def update_preview_panel(self):
        # 跨頁循環靜默時跳過
        if self.inLoopMode or getattr(self, "_suppressPreviewUpdate", False):
            return
        items = self.sliceList.selectedItems()
        if items:
            slice_item = items[0].data(Qt.UserRole)
            try:
                self.previewPanel.update_preview(slice_item)
            except Exception:
                # 可能在場景切換過程中，引用的切片已被 Qt 釋放
                self.previewPanel.update_preview(None)
        else:
            self.previewPanel.update_preview(None)

# 以下為對齊與分布的實作
    def align_left(self):
        sel = [s for s in self.sliceView.scene().selectedItems() if isinstance(s, SliceRect)]
        x0 = min(s.rect().x() for s in sel)
        for s in sel:
            r = s.rect()
            s.setRect(QRectF(x0, r.y(), r.width(), r.height()))
        self.updateSliceList(); self.markProjectEdited()

    def align_hcenter(self):
        sel = [s for s in self.sliceView.scene().selectedItems() if isinstance(s, SliceRect)]
        xs = [s.rect().x() for s in sel]
        widths = [s.rect().width() for s in sel]
        min_x, max_r = min(xs), max(x + w for x, w in zip(xs, widths))
        mid = (min_x + max_r) / 2
        for s in sel:
            r = s.rect()
            s.setRect(QRectF(mid - r.width()/2, r.y(), r.width(), r.height()))
        self.updateSliceList(); self.markProjectEdited()

    def align_right(self):
        sel = [s for s in self.sliceView.scene().selectedItems() if isinstance(s, SliceRect)]
        max_r = max(s.rect().x() + s.rect().width() for s in sel)
        for s in sel:
            r = s.rect()
            s.setRect(QRectF(max_r - r.width(), r.y(), r.width(), r.height()))
        self.updateSliceList(); self.markProjectEdited()

    def distribute_vertical(self):
        sel = sorted([s for s in self.sliceView.scene().selectedItems() if isinstance(s, SliceRect)], key=lambda s: s.rect().y())
        tops = [s.rect().y() for s in sel]
        bottoms = [s.rect().y() + s.rect().height() for s in sel]
        y0, y1 = min(tops), max(bottoms)
        total_h = sum(s.rect().height() for s in sel)
        space = (y1 - y0 - total_h) / (len(sel) - 1)
        cur = y0
        for s in sel:
            h = s.rect().height()
            s.setRect(QRectF(s.rect().x(), cur, s.rect().width(), h))
            cur += h + space
        self.updateSliceList(); self.markProjectEdited()

    def align_top(self):
        sel = [s for s in self.sliceView.scene().selectedItems() if isinstance(s, SliceRect)]
        y0 = min(s.rect().y() for s in sel)
        for s in sel:
            r = s.rect()
            s.setRect(QRectF(r.x(), y0, r.width(), r.height()))
        self.updateSliceList(); self.markProjectEdited()

    def align_vcenter(self):
        sel = [s for s in self.sliceView.scene().selectedItems() if isinstance(s, SliceRect)]
        ys = [s.rect().y() for s in sel]
        heights = [s.rect().height() for s in sel]
        min_y, max_b = min(ys), max(y + h for y, h in zip(ys, heights))
        mid = (min_y + max_b) / 2
        for s in sel:
            r = s.rect()
            s.setRect(QRectF(r.x(), mid - r.height()/2, r.width(), r.height()))
        self.updateSliceList(); self.markProjectEdited()

    def align_bottom(self):
        sel = [s for s in self.sliceView.scene().selectedItems() if isinstance(s, SliceRect)]
        max_b = max(s.rect().y() + s.rect().height() for s in sel)
        for s in sel:
            r = s.rect()
            s.setRect(QRectF(r.x(), max_b - r.height(), r.width(), r.height()))
        self.updateSliceList(); self.markProjectEdited()

    def distribute_horizontal(self):
        sel = sorted([s for s in self.sliceView.scene().selectedItems() if isinstance(s, SliceRect)], key=lambda s: s.rect().x())
        xs = [s.rect().x() for s in sel]
        rights = [s.rect().x() + s.rect().width() for s in sel]
        x0, x1 = min(xs), max(rights)
        total_w = sum(s.rect().width() for s in sel)
        space = (x1 - x0 - total_w) / (len(sel) - 1)
        cur = x0
        for s in sel:
            w = s.rect().width()
            s.setRect(QRectF(cur, s.rect().y(), w, s.rect().height()))
            cur += w + space
        self.updateSliceList(); self.markProjectEdited()

    def loadLayout(self):
        settings = QSettings(self.settings_organization, self.settings_application)
        geometry = settings.value("geometry")
        state = settings.value("windowState")
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)
        auto_process_visible = settings.value("autoProcessPanelVisible", "true")
        self.auto_process_panel.setVisible(auto_process_visible == "true")
        preview_visible = settings.value("previewPanelVisible", "true")
        self.previewPanel.setVisible(preview_visible == "true")
        ruler = settings.value("rulerVisible", "true") == "true"
        self.sliceView.showRulers = ruler
        self.actToggleRuler.setChecked(ruler)
        align_visible = settings.value("alignPanelVisible", "false")
        self.findChild(QDockWidget, "dockAlign").setVisible(align_visible == "true")
        self.actToggleAlign.setChecked(align_visible == "true")
        # 査找切片面板可見性
        find_visible = settings.value("findPanelVisible", "false")
        try:
            self.findChild(QDockWidget, "dockFind").setVisible(find_visible == "true")
        except Exception:
            pass
        if hasattr(self, 'actToggleFind'):
            self.actToggleFind.setChecked(find_visible == "true")

    # 根據 sliceList 的順序更新切片的 number 並刷新列表
    def reorderSlices(self):
        for index in range(self.sliceList.count()):
            item = self.sliceList.item(index)
            slice_item = item.data(Qt.UserRole)
            if slice_item:
                slice_item.number = index + 1
        self.updateSliceList()

    # 置頂
    def topSlice(self):
        if self.sliceList.count() == 0:
            return
        items = []
        for i in range(self.sliceList.count()):
            lw_item = self.sliceList.item(i)
            items.append((lw_item.data(Qt.UserRole), lw_item.isSelected()))
        # 將所有被選項移至最前方，保持相對順序
        new_order = [x for x in items if x[1]] + [x for x in items if not x[1]]
        for index, (s, _) in enumerate(new_order):
            s.number = index + 1
        self.updateSliceList()
        self.markProjectEdited()

    # 上移
    def upSlice(self):
        count = self.sliceList.count()
        if count == 0:
            return
        items = []
        for i in range(count):
            lw_item = self.sliceList.item(i)
            items.append((lw_item.data(Qt.UserRole), lw_item.isSelected()))
        # 從上至下檢査：若當前被選中且前一項未被選中，與前者交換
        for i in range(1, len(items)):
            if items[i][1] and not items[i-1][1]:
                items[i-1], items[i] = items[i], items[i-1]
        for index, (s, _) in enumerate(items):
            s.number = index + 1
        self.updateSliceList()
        self.markProjectEdited()

    # 下移
    def downSlice(self):
        count = self.sliceList.count()
        if count == 0:
            return
        items = []
        for i in range(count):
            lw_item = self.sliceList.item(i)
            items.append((lw_item.data(Qt.UserRole), lw_item.isSelected()))
        # 從下至上檢査：若當前被選中且下一項未被選中，與下一項交換
        for i in range(len(items) - 2, -1, -1):
            if items[i][1] and not items[i+1][1]:
                items[i], items[i+1] = items[i+1], items[i]
        for index, (s, _) in enumerate(items):
            s.number = index + 1
        self.updateSliceList()
        self.markProjectEdited()

    # 置底
    def bottomSlice(self):
        if self.sliceList.count() == 0:
            return
        items = []
        for i in range(self.sliceList.count()):
            lw_item = self.sliceList.item(i)
            items.append((lw_item.data(Qt.UserRole), lw_item.isSelected()))
        # 將所有被選項移至後方，保持相對順序
        new_order = [x for x in items if not x[1]] + [x for x in items if x[1]]
        for index, (s, _) in enumerate(new_order):
            s.number = index + 1
        self.updateSliceList()
        self.markProjectEdited()

    def updateSliceList(self):
        # 跨頁循環靜默時跳過
        if self.inLoopMode:
            return
        # 重新編號所有切片(避免存在重複編號)
        slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        slices.sort(key=lambda s: s.number)
        for i, s in enumerate(slices):
            s.number = i + 1

        # 保存所有選中的切片
        selected_slices = set(item.data(Qt.UserRole) for item in self.sliceList.selectedItems())
        self.sliceList.clear()
        for s in slices:
            rect = s.rect()
            x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
            if s.name:
                text = tr('切片 {0} | {1}（{2},{3} | {4}x{5}）').format(s.number, s.name, x, y, w, h)
            else:
                text = tr('切片 {0}（{1},{2} | {3}x{4}）').format(s.number, x, y, w, h)
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, s)
            item.setToolTip(text)
            self.sliceList.addItem(item)
            # 保持之前選中狀態
            if s in selected_slices:
                item.setSelected(True)
        # 如果沒有任何項目被選中，更新狀態欄
        if not selected_slices:
            self.statusBar().showMessage(tr("已取消選擇"))

    def onSliceItemClicked(self, item):
        if item.isSelected() and len(self.sliceList.selectedItems()) == 1:
            s = item.data(Qt.UserRole)
            if s:
                rect = s.rect()
                self.statusBar().showMessage(
                    tr('已選擇：切片 {0}（X:{1} Y:{2} 寬:{3} 高:{4}）').format(s.number, int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))
                )
                # 當單選時，視圖自動移動到該切片所在位置
                self.sliceView.centerOn(s)
        else:
            self.statusBar().showMessage(tr('已選擇 {0} 份切片').format(len(self.sliceList.selectedItems())))

    # 根據切片列表多選狀態更新視圖中切片的選中狀態
    def onSliceSelectionChanged(self):
        # 同步更新視圖中所有切片的選中狀態，根據列表選擇狀態設定
        self.sliceView.scene().blockSignals(True)
        for i in range(self.sliceList.count()):
            list_item = self.sliceList.item(i)
            s = list_item.data(Qt.UserRole)
            if list_item.isSelected():
                s.setSelected(True)
            else:
                s.setSelected(False)
        self.sliceView.scene().blockSignals(False)
        # 更新狀態欄訊息
        selected_count = len(self.sliceList.selectedItems())
        if selected_count == 0:
            self.statusBar().showMessage(tr("已取消選擇"))
        elif selected_count > 1:
            self.statusBar().showMessage(tr('已選擇 {0} 份切片').format(selected_count))
        else:
            # 單選時顯示切片詳細資訊
            item = self.sliceList.selectedItems()[0]
            s = item.data(Qt.UserRole)
            if s:
                rect = s.rect()
                self.statusBar().showMessage(
                    tr('已選擇：切片 {0}（X:{1} Y:{2} 寬:{3} 高:{4}）').format(s.number, int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))
                )
            else:
                self.statusBar().showMessage(tr("已選擇 1 份切片"))

    # 根據預覽畫面中的選取狀態，更新左側列表中的項目選中狀態
    def syncListSelectionWithScene(self):
        # 避免重入
        self.sliceList.blockSignals(True)
        selected_slices = set(self.sliceView.scene().selectedItems())
        for i in range(self.sliceList.count()):
            list_item = self.sliceList.item(i)
            s = list_item.data(Qt.UserRole)
            if s in selected_slices:
                list_item.setSelected(True)
                self.sliceList.scrollToItem(list_item)  # 滾動至所選項目
            else:
                list_item.setSelected(False)
        self.sliceList.blockSignals(False)
        # 根據選中情況更新狀態欄
        count = len(selected_slices)
        if count == 0:
            self.statusBar().showMessage(tr("已取消選擇"))
        elif count > 1:
            self.statusBar().showMessage(tr('已選擇 {0} 份切片').format(count))
        else:
            selected_slice = next(iter(selected_slices))
            rect = selected_slice.rect()
            self.statusBar().showMessage(
                tr('已選擇：切片 {0}（X:{1} Y:{2} 寬:{3} 高:{4}）').format(selected_slice.number, int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))
            )

    def _set_action_icon(self, action, icon_name: str) -> None:
        self._themed_icons.append((action, icon_name))
        action.setIcon(make_icon(icon_name, dark=theme_manager.resolved_theme == "dark"))

    def _set_menu_icon(self, menu, icon_name: str) -> None:
        self._themed_menus.append((menu, icon_name))
        menu.setIcon(make_icon(icon_name, dark=theme_manager.resolved_theme == "dark"))

    def _set_button_icon(self, button, icon_name: str) -> None:
        self._themed_buttons.append((button, icon_name))
        button.setIcon(make_icon(icon_name, dark=theme_manager.resolved_theme == "dark"))
        button.setIconSize(QSize(16, 16))

    def _refresh_icons(self) -> None:
        dark = theme_manager.resolved_theme == "dark"
        for action, icon_name in getattr(self, "_themed_icons", []):
            action.setIcon(make_icon(icon_name, dark=dark))
        for menu, icon_name in getattr(self, "_themed_menus", []):
            menu.setIcon(make_icon(icon_name, dark=dark))
        for button, icon_name in getattr(self, "_themed_buttons", []):
            button.setIcon(make_icon(icon_name, dark=dark))

    def createToolBar(self):
        toolbar = self.addToolBar(tr("工具"))
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(16, 16))
        fileMenu = QMenu(tr("導入"), self)
        actOpenImg = QAction(tr("導入圖片"), self)
        actOpenImg.triggered.connect(self.openImage)
        actOpenImg.setShortcut("Ctrl+O")
        fileMenu.addAction(actOpenImg)
        actOpenFolder = QAction(tr("導入文件夾"), self)
        actOpenFolder.triggered.connect(self.openFolder)
        actOpenFolder.setShortcut("Ctrl+Shift+O")
        fileMenu.addAction(actOpenFolder)
        actOpenProject = QAction(tr("導入工程"), self)
        actOpenProject.triggered.connect(self.openProject)
        actOpenProject.setShortcut("Ctrl+P")
        fileMenu.addAction(actOpenProject)
        # 「設定/清除預設工程」動作
        default_project_text = tr("設定預設工程") if self.defaultProjectPath is None else tr("清除預設工程")
        self.actDefaultProject = QAction(default_project_text, self)
        self.actDefaultProject.triggered.connect(self.toggleDefaultProject)
        fileMenu.addAction(self.actDefaultProject)
        # 「導入看典古籍json」選項
        actOpenKandian = QAction(tr("導入看典古籍json"), self)
        actOpenKandian.triggered.connect(self.importKandianJson)
        fileMenu.addAction(actOpenKandian)
        # 「設定/清除json導入預設」動作
        preset_text = tr("設定json導入預設") if self.jsonImportPreset is None else tr("清除json導入預設")
        self.actJsonImportPreset = QAction(preset_text, self)
        self.actJsonImportPreset.triggered.connect(self.toggleJsonImportPreset)
        fileMenu.addAction(self.actJsonImportPreset)
        # Quick actions are added to the icon strip after all menus exist.
        
        exportMenu = QMenu(tr("導出"), self)
        actExportSlices = QAction(tr("導出切片"), self)
        actExportSlices.triggered.connect(self.exportSlices)
        actExportSlices.setShortcut("Ctrl+E")
        exportMenu.addAction(actExportSlices)
        # 修改導出預設動作，使用 self.actUpdateDefault 保存
        self.actUpdateDefault = QAction(tr("設定導出預設"), self)
        self.actUpdateDefault.triggered.connect(self.updateExportDefaults)
        exportMenu.addAction(self.actUpdateDefault)
        actSaveProject = QAction(tr("保存工程"), self)
        actSaveProject.triggered.connect(self.saveProject)
        actSaveProject.setShortcut("Ctrl+S")
        exportMenu.addAction(actSaveProject)
        actSaveProjectAs = QAction(tr("工程另存爲"), self)
        actSaveProjectAs.triggered.connect(self.saveProjectAs)
        actSaveProjectAs.setShortcut("Ctrl+Shift+S")
        exportMenu.addAction(actSaveProjectAs)

        
        # 動作下拉選單
        actionMenu = QMenu(tr("動作"), self)
        actAutoRecognize = QAction(tr("自動識別切片"), self)
        actAutoRecognize.triggered.connect(self.autoRecognizeWordSlices)
        actAutoRecognize.setShortcut("Ctrl+R")
        actionMenu.addAction(actAutoRecognize)
        actDetectTable = QAction(tr("自動識別表格"), self)
        actDetectTable.triggered.connect(self.autoDetectTable)
        actionMenu.addAction(actDetectTable)
        actDetectTable.setShortcut("Ctrl+T")
        actDivide = QAction(tr("劃分切片"), self)
        actDivide.triggered.connect(self.openDivideSlicesDialog)
        actionMenu.addAction(actDivide)
        actDivide.setShortcut("Ctrl+D")
        actMove = QAction(tr("移動切片"), self)
        actMove.triggered.connect(self.openMoveSlicesDialog)
        actionMenu.addAction(actMove)
        actMove.setShortcut("Ctrl+M")
        actScale = QAction(tr("縮放切片"), self)
        actScale.triggered.connect(self.openScaleSlicesDialog)
        actionMenu.addAction(actScale)
        actScale.setShortcut("Ctrl+L")
        actScaleProject = QAction(tr("縮放工程座標"), self)
        actScaleProject.triggered.connect(self.openScaleProjectDialog)
        actionMenu.addAction(actScaleProject)
        actScaleProject.setShortcut("Ctrl+Shift+L")
        actFilter = QAction(tr("篩除切片"), self)
        actFilter.triggered.connect(self.filterSlices)
        actionMenu.addAction(actFilter)
        actFilter.setShortcut("Ctrl+F")
        actNormalize = QAction(tr("切片定幅"), self)
        actNormalize.triggered.connect(self.openNormalizeSlicesDialog)
        actionMenu.addAction(actNormalize)
        actNormalize.setShortcut("Ctrl+I")
        actMerge = QAction(tr("合併重疊切片"), self)
        actMerge.triggered.connect(self.mergeOverlappingSlices)
        actionMenu.addAction(actMerge)
        actMerge.setShortcut("Ctrl+G")
        actBatchRename = QAction(tr("批量重命名"), self)
        actBatchRename.triggered.connect(self.openBatchRenameDialog)
        actionMenu.addAction(actBatchRename)
        actBatchRename.setShortcut("Ctrl+N")


        windowMenu = QMenu(tr("窗口"), self)
        
        # 切片列表
        actToggleSliceList = QAction(tr("切片列表"), self)
        actToggleSliceList.setCheckable(True)
        actToggleSliceList.setChecked(True)
        actToggleSliceList.toggled.connect(lambda checked: self.findChild(QDockWidget, "dockList").setVisible(checked))
        self.actToggleSliceList = actToggleSliceList
        windowMenu.addAction(actToggleSliceList)

        # 定幅切片
        actToggleDimension = QAction(tr("定幅切片"), self)
        actToggleDimension.setCheckable(True)
        actToggleDimension.setChecked(True)
        actToggleDimension.toggled.connect(lambda checked: self.findChild(QDockWidget, "dockDim").setVisible(checked))
        self.actToggleDimension = actToggleDimension
        windowMenu.addAction(actToggleDimension)

        # 裁剪校正
        actToggleStraighten = QAction(tr("裁剪校正"), self)
        actToggleStraighten.setCheckable(True)
        actToggleStraighten.setChecked(True)
        actToggleStraighten.toggled.connect(lambda checked: self.findChild(QDockWidget, "dockStraight").setVisible(checked))
        self.actToggleStraighten = actToggleStraighten
        windowMenu.addAction(actToggleStraighten)

        # 對齊與分布
        actToggleAlign = QAction(tr("對齊與分布"), self)
        actToggleAlign.setCheckable(True)
        actToggleAlign.setChecked(True)
        actToggleAlign.toggled.connect(lambda v: self.findChild(QDockWidget, "dockAlign").setVisible(v))
        windowMenu.addAction(actToggleAlign)
        self.actToggleAlign = actToggleAlign

        # 自動處理
        actToggleAutoProcess = QAction(tr("自動處理"), self)
        actToggleAutoProcess.setCheckable(True)
        actToggleAutoProcess.setChecked(True)
        actToggleAutoProcess.toggled.connect(lambda checked: self.auto_process_panel.setVisible(checked))
        self.actToggleAutoProcess = actToggleAutoProcess
        windowMenu.addAction(actToggleAutoProcess)

        # 預覽
        actTogglePreviewPanel = QAction(tr("切片預覽"), self)
        actTogglePreviewPanel.setCheckable(True)
        actTogglePreviewPanel.setChecked(True)
        actTogglePreviewPanel.toggled.connect(lambda checked: self.previewPanel.setVisible(checked))
        self.actTogglePreviewPanel = actTogglePreviewPanel
        windowMenu.addAction(actTogglePreviewPanel)
        
        # 査找切片面板
        actToggleFind = QAction(tr("査找切片"), self)
        actToggleFind.setCheckable(True)
        actToggleFind.setChecked(False)
        actToggleFind.toggled.connect(lambda checked: self.findChild(QDockWidget, "dockFind").setVisible(checked))
        self.actToggleFind = actToggleFind
        windowMenu.addAction(actToggleFind)

        # 標尺
        actToggleRuler = QAction(tr("標尺"), self)
        actToggleRuler.setCheckable(True)
        actToggleRuler.setChecked(True)
        actToggleRuler.toggled.connect(lambda v: (
            setattr(self.sliceView, "showRulers", v),
            self.sliceView.viewport().update()
        ))
        self.actToggleRuler = actToggleRuler
        windowMenu.addAction(actToggleRuler)
        windowMenu.addSeparator()
        actResetLayout = QAction(tr("重設面板佈局"), self)
        actResetLayout.triggered.connect(lambda: self.resetDockLayout())
        windowMenu.addAction(actResetLayout)

        # 每次下拉前同步各面板顯隱狀態
        windowMenu.aboutToShow.connect(self.syncWindowMenuActions)



        helpMenu = QMenu(tr("幫助"), self)
        actManual = QAction(tr("操作指南"), self)
        actManual.triggered.connect(self.showManual)
        helpMenu.addAction(actManual)
        actCheckUpdate = QAction(tr("檢査更新"), self)
        actCheckUpdate.triggered.connect(self.checkUpdate)
        helpMenu.addAction(actCheckUpdate)
        actAbout = QAction(tr("關於"), self)
        actAbout.triggered.connect(self.showAbout)
        helpMenu.addAction(actAbout)


        settingsMenu = QMenu(tr("設定"), self)

        self.actCommandPalette = QAction(tr("命令面板"), self)
        self.actCommandPalette.setShortcut("Ctrl+K")
        self._set_action_icon(self.actCommandPalette, "command")
        self.actCommandPalette.triggered.connect(self.showCommandPalette)
        self.actCommandPalette.setShortcutContext(Qt.WindowShortcut)
        settingsMenu.addAction(self.actCommandPalette)
        self.addAction(self.actCommandPalette)
        settingsMenu.addSeparator()

        themeMenu = QMenu(tr("外觀"), settingsMenu)
        self._set_menu_icon(themeMenu, "theme")
        self.themeActions = {}
        for theme_code, theme_name in AVAILABLE_THEMES:
            theme_action = QAction(tr(theme_name), self)
            theme_action.setCheckable(True)
            theme_action.setChecked(theme_code == theme_manager.setting)
            theme_action.triggered.connect(
                lambda _checked=False, code=theme_code: self.changeTheme(code)
            )
            themeMenu.addAction(theme_action)
            self.themeActions[theme_code] = theme_action
        settingsMenu.addMenu(themeMenu)

        languageMenu = QMenu(tr("語言"), settingsMenu)
        self._set_menu_icon(languageMenu, "language")
        self.languageActions = {}
        for locale_code, locale_name in AVAILABLE_LANGUAGES:
            language_action = QAction(locale_name, self)
            language_action.setCheckable(True)
            language_action.setChecked(locale_code == i18n.language)
            language_action.triggered.connect(
                lambda _checked=False, code=locale_code: self.changeLanguage(code)
            )
            languageMenu.addAction(language_action)
            self.languageActions[locale_code] = language_action
        settingsMenu.addMenu(languageMenu)



        navToolbar = self.addToolBar(tr("導航"))
        self.navToolbar = navToolbar
        navToolbar.setObjectName("navToolbar")
        navToolbar.setMovable(False)
        navToolbar.setFloatable(False)
        navToolbar.setIconSize(QSize(18, 18))
        navToolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        prevAct = QAction(tr("上一張"), self)
        self._set_action_icon(prevAct, "chevron-left")
        prevAct.triggered.connect(self.prevImage)
        prevAct.setShortcut("Ctrl+Left")
        navToolbar.addAction(prevAct)
        self.imageJumpSpin = QSpinBox(self)
        self.imageJumpSpin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.imageJumpSpin.setMinimum(1)
        self.imageJumpSpin.setMaximum(len(self.folderImages) if self.folderImages else 1)
        self.imageJumpSpin.setValue(self.currentImageIndex + 1 if self.folderImages else 1)
        self.imageJumpSpin.setFixedWidth(40)
        self.imageJumpSpin.setToolTip(tr("跳轉圖片"))
        self.imageJumpSpin.editingFinished.connect(self.jumpToImage)
        self.imageJumpSpin.installEventFilter(self)
        self.imageTotalLabel = QLabel("", self)
        self.imageTotalLabel.setText(f"/{len(self.folderImages)}" if self.folderImages else "/1")
        jumpWidget = QWidget(self)
        jumpLayout = QHBoxLayout(jumpWidget)
        jumpLayout.setContentsMargins(0, 0, 0, 0)
        jumpLayout.addWidget(self.imageJumpSpin)
        jumpLayout.addWidget(self.imageTotalLabel)
        navToolbar.addWidget(jumpWidget)
        nextAct = QAction(tr("下一張"), self)
        self._set_action_icon(nextAct, "chevron-right")
        nextAct.triggered.connect(self.nextImage)
        nextAct.setShortcut("Ctrl+Right")
        navToolbar.addAction(nextAct)

        self.actToggleNavToolbar = QAction(tr("導航"), self)
        self.actToggleNavToolbar.setCheckable(True)
        self.actToggleNavToolbar.setChecked(True)
        self.actToggleNavToolbar.toggled.connect(self.navToolbar.setVisible)
        windowMenu.insertAction(actResetLayout, self.actToggleNavToolbar)

        # 縮放欄
        zoomToolbar = self.addToolBar(tr("縮放"))
        zoomToolbar.setObjectName("zoomToolbar")
        zoomToolbar.setMovable(False)
        zoomToolbar.setFloatable(False)
        zoomToolbar.setIconSize(QSize(18, 18))
        zoomToolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        # 縮小按鈕
        zoomOutAct = QAction(tr("縮小"), self)
        self._set_action_icon(zoomOutAct, "zoom-out")
        zoomOutAct.triggered.connect(lambda: (self.sliceView.zoomOut(), self._updateZoomCombo()))
        zoomToolbar.addAction(zoomOutAct)
        # 縮放比輸入+下拉
        from PyQt5.QtWidgets import QComboBox
        zoomCombo = QComboBox(self)
        zoomCombo.setEditable(True)
        presets = ["50%", "75%", "100%", "150%", "200%", "500%", tr("符合寬度"), tr("符合頁面")]
        zoomCombo.addItems(presets)
        zoomCombo.setCurrentText("100%")
        def applyZoom(text):
            text = text.strip()
            view = self.sliceView
            if text.endswith("%") and text[:-1].isdigit():
                # 直接按百分比縮放
                f = int(text[:-1]) / 100.0
            elif text == tr("符合寬度"):
                # 檢査是否有圖片導入
                if not view.image_item or not view.image_item.pixmap():
                    self.statusBar().showMessage(tr("請先導入圖片"))
                    zoomCombo.setCurrentText("100%")
                    return
                # 寬度填滿
                w = view.viewport().width()
                img_w = view.image_item.pixmap().width()
                f = w / img_w if img_w else 1
                # 整數百分比
                f = int(f * 100) / 100.0
            elif text == tr("符合頁面"):
                # 檢査是否有圖片導入
                if not view.image_item or not view.image_item.pixmap():
                    self.statusBar().showMessage(tr("請先導入圖片"))
                    zoomCombo.setCurrentText("100%")
                    return
                # 寬度與高度最小的那個
                vw, vh = view.viewport().width(), view.viewport().height()
                pw, ph = view.image_item.pixmap().width(), view.image_item.pixmap().height()
                fx = vw / pw if pw else 1
                fy = vh / ph if ph else 1
                f = min(fx, fy)
                f = int(f * 100) / 100.0
            else:
                return
            view.resetTransform()
            view.scale(f, f)
            # 用整數百分比更新輸入框
            zoomCombo.setCurrentText(f"{int(f*100)}%")
        zoomCombo.lineEdit().returnPressed.connect(lambda: applyZoom(zoomCombo.currentText()))
        zoomCombo.activated[str].connect(applyZoom)
        zoomToolbar.addWidget(zoomCombo)
        self.zoomCombo = zoomCombo
        # 放大按鈕
        zoomInAct = QAction(tr("放大"), self)
        self._set_action_icon(zoomInAct, "zoom-in")
        zoomInAct.triggered.connect(lambda: (self.sliceView.zoomIn(), self._updateZoomCombo()))
        zoomToolbar.addAction(zoomInAct)

        # Photoshop-like application menu bar.
        menu_bar = self.menuBar()
        if hasattr(menu_bar, "setNativeMenuBar"):
            menu_bar.setNativeMenuBar(False)
        menu_bar.clear()
        for menu in (fileMenu, exportMenu, actionMenu, windowMenu, helpMenu, settingsMenu):
            menu_bar.addMenu(menu)

        # Quick-action icon strip (the equivalent of Photoshop's options bar).
        self._set_action_icon(actOpenImg, "image")
        self._set_action_icon(actOpenFolder, "folder")
        self._set_action_icon(actOpenProject, "project")
        self._set_action_icon(actSaveProject, "save")
        self._set_action_icon(actExportSlices, "export")
        self._set_action_icon(actAutoRecognize, "wand")
        self._set_action_icon(actDetectTable, "table")
        self._set_action_icon(actDivide, "grid")
        self._set_action_icon(actMove, "move")
        self._set_action_icon(actScale, "scale")
        self._set_action_icon(actScaleProject, "ruler")
        self._set_action_icon(actFilter, "filter")
        self._set_action_icon(actNormalize, "frame")
        self._set_action_icon(actMerge, "merge")
        self._set_action_icon(actBatchRename, "text")
        self._set_action_icon(actManual, "manual")
        self._set_action_icon(actCheckUpdate, "update")
        self._set_action_icon(actAbout, "info")
        self._set_action_icon(actResetLayout, "frame")

        toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        toolbar.setIconSize(QSize(18, 18))
        for action in (actOpenImg, actOpenFolder, actOpenProject):
            toolbar.addAction(action)
        toolbar.addSeparator()
        for action in (actSaveProject, actExportSlices):
            toolbar.addAction(action)
        toolbar.addSeparator()
        for action in (
            actAutoRecognize,
            actDetectTable,
            actDivide,
            actMove,
            actScale,
            actScaleProject,
            actFilter,
            actNormalize,
            actMerge,
            actBatchRename,
        ):
            toolbar.addAction(action)
        toolbar.addSeparator()
        toolbar.addAction(self.actCommandPalette)

    def _updateZoomCombo(self):
        # 同步 SliceView 變換後的縮放比到輸入框
        f = self.sliceView.transform().m11()
        self.zoomCombo.setCurrentText(f"{int(f*100)}%")

    def syncWindowMenuActions(self):
        if hasattr(self, "actToggleNavToolbar"):
            self.actToggleNavToolbar.setChecked(self.navToolbar.isVisible())
        # 同步「窗口」選單項的勾選狀態
        self.actToggleSliceList.setChecked(self.findChild(QDockWidget, "dockList").isVisible())
        self.actToggleDimension.setChecked(self.findChild(QDockWidget, "dockDim").isVisible())
        self.actToggleStraighten.setChecked(self.findChild(QDockWidget, "dockStraight").isVisible())
        self.actToggleAutoProcess.setChecked(self.auto_process_panel.isVisible())
        self.actTogglePreviewPanel.setChecked(self.previewPanel.isVisible())
        self.actToggleAlign.setChecked(self.findChild(QDockWidget, "dockAlign").isVisible())
        # 査找切片面板
        if hasattr(self, 'actToggleFind'):
            try:
                self.actToggleFind.setChecked(self.findChild(QDockWidget, "dockFind").isVisible())
            except Exception:
                pass

    # 切換json導入預設的處理函數
    def toggleJsonImportPreset(self):
        if self.jsonImportPreset is None:
            dlg = JsonImportPresetDialog(parent=self)
            if dlg.exec_() == QDialog.Accepted:
                self.jsonImportPreset = dlg.getValues()
                self.actJsonImportPreset.setText(tr("清除json導入預設"))
                self.statusBar().showMessage(tr("json導入預設已設定"))
        else:
            self.jsonImportPreset = None
            self.actJsonImportPreset.setText(tr("設定json導入預設"))
            self.statusBar().showMessage(tr("json導入預設已清除"))

    # 切換預設工程的處理函數
    def toggleDefaultProject(self):
        if self.defaultProjectPath is None:
            path, _ = QFileDialog.getOpenFileName(self, tr("選擇預設工程文件"), "", tr("工程文件 (*.cutter)"))
            if path:
                self.defaultProjectPath = path
                self.actDefaultProject.setText(tr("清除預設工程"))
                self.statusBar().showMessage(tr('預設工程已設定：{0}').format(os.path.basename(path)))
        else:
            self.defaultProjectPath = None
            self.actDefaultProject.setText(tr("設定預設工程"))
            self.statusBar().showMessage(tr("預設工程已清除"))

    def updateExportDefaults(self):
        if self.defaultExportDir and self.defaultExportFormat:
            self.defaultExportDir = ""
            self.defaultExportFormat = ""
            self.actUpdateDefault.setText(tr("設定導出預設"))
            self.statusBar().showMessage(tr("導出預設已清除"))
        else:
            dir_path = QFileDialog.getExistingDirectory(self, tr("選擇預設導出目錄"), self.defaultExportDir)
            if dir_path:
                self.defaultExportDir = dir_path
            formats = ["PNG", "JPG", "BMP"]
            try:
                current_index = formats.index(self.defaultExportFormat)
            except ValueError:
                current_index = 0
            fmt, ok = QInputDialog.getItem(self, tr("設定預設格式"), tr("導出格式："), formats, current_index, False)
            if ok:
                self.defaultExportFormat = fmt
                self.actUpdateDefault.setText(tr("清除導出預設"))
                self.statusBar().showMessage(tr('更新導出預設：格式爲 {0}；目錄爲 {1}').format(fmt, self.defaultExportDir))

    # 導入文件夾
    def loadFolderPath(self, folder: str) -> None:
        if not folder or not os.path.isdir(folder):
            return
        self.currentFolder = folder
        self.folderImages = sorted(
            os.path.join(folder, name)
            for name in os.listdir(folder)
            if name.lower().endswith(IMAGE_EXTENSIONS)
        )
        if self.folderImages:
            self.currentImageIndex = 0
            self.loadCurrentFolderImage()
        self.auto_process_panel.update_loop_button_state()

    def openFolder(self):
        folder = QFileDialog.getExistingDirectory(self, tr("選擇文件夾"), "")
        if folder:
            self.loadFolderPath(folder)

    def loadCurrentFolderImage(self):
        path = self.folderImages[self.currentImageIndex]
        # 在載入新圖片前先清空列表並抑制預覽更新，避免 scene 清空時引用已刪除切片
        self._suppressPreviewUpdate = True
        self.sliceList.clear()
        self.sliceView.loadImage(path)
        filename = os.path.basename(path)
        self.statusBar().showMessage(tr('載入圖片：{0}').format(filename))
        self.originalBaseName = os.path.splitext(filename)[0]
        self.currentImagePath = path  # 儲存圖片路徑
        # 更新跳轉 widget 資訊
        if self.folderImages:
            count = len(self.folderImages)
            self.imageJumpSpin.setMaximum(count)
            self.imageJumpSpin.setValue(self.currentImageIndex + 1)
            self.imageTotalLabel.setText(f"/{count}")
        self.checkAndLoadProject()     # 自動檢査工程文件
        # 恢復預覽更新並刷新一次
        self._suppressPreviewUpdate = False
        try:
            self.update_preview_panel()
        except Exception:
            pass

    # 圖片導航前確認是否捨棄現有切片
    def getCurrentProjectData(self):
        slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        slices.sort(key=lambda s: s.number)
        # 與 writeProjectFile 完全一致：X Y 寬 高 名稱（名稱可能為空）
        return "\n".join([
            "\t".join([
                str(int(item.rect().x())),
                str(int(item.rect().y())),
                str(int(item.rect().width())),
                str(int(item.rect().height())),
                getattr(item, "name", "") or ""
            ]) for item in slices
        ])

    def confirmDiscardSlices(self):
        if not self.currentImagePath:
            return True
        # 如果當前工程與上次保存的內容相同，視為沒有修改
        try:
            current_data = self.getCurrentProjectData()
        except Exception:
            current_data = None
        if current_data is not None and current_data == getattr(self, "_last_saved_project_data", ""):
            return True
        QApplication.beep()
        msgBox = QMessageBox(self)
        msgBox.setWindowTitle(tr("保存工程"))
        msgBox.setText(tr("要保存當前工程嗎？"))
        btnSave = msgBox.addButton(tr("保存"), QMessageBox.AcceptRole)
        btnDont = msgBox.addButton(tr("不保存"), QMessageBox.DestructiveRole)
        btnCancel = msgBox.addButton(tr("取消"), QMessageBox.RejectRole)
        msgBox.exec_()
        if msgBox.clickedButton() == btnSave:
            try:
                self.saveProject()
            except Exception as e:
                QMessageBox.warning(self, tr("錯誤"), tr('保存失敗：{0}').format(e))
                return False
            return True
        elif msgBox.clickedButton() == btnDont:
            return True
        else:
            return False

    def closeEvent(self, event):
        if self.confirmDiscardSlices():
            # 保存佈局
            settings = QSettings(self.settings_organization, self.settings_application)
            settings.setValue("geometry", self.saveGeometry())
            settings.setValue("windowState", self.saveState())
            settings.setValue("autoProcessPanelVisible", "true" if self.auto_process_panel.isVisible() else "false")
            settings.setValue("previewPanelVisible", "true" if self.previewPanel.isVisible() else "false")
            settings.setValue("rulerVisible", "true" if self.sliceView.showRulers else "false")
            settings.setValue("alignPanelVisible", "true" if self.findChild(QDockWidget, "dockAlign").isVisible() else "false")
            # 査找切片面板可見性
            try:
                settings.setValue("findPanelVisible", "true" if self.findChild(QDockWidget, "dockFind").isVisible() else "false")
            except Exception:
                pass
            event.accept()
        else:
            event.ignore()

    def nextImage(self):
        # 防止重入（例如快捷鍵與 QAction 同時觸發）
        if getattr(self, "_navigating", False):
            return
        self._navigating = True
        try:
            # 跨頁循環模式下僅更新索引並載入新圖（不觸發其他 UI 更新）
            if self.inLoopMode:
                if self.currentImageIndex < len(self.folderImages) - 1:
                    self.currentImageIndex += 1
                    self.loadCurrentFolderImage()
                return
            if not self.folderImages:
                QApplication.beep()   # 無文件夾時發聲
                self.statusBar().showMessage(tr("請先導入文件夾"))
                return
            if not self.confirmDiscardSlices():
                return
            if self.currentImageIndex < len(self.folderImages) - 1:
                self.currentImageIndex += 1
                self.loadCurrentFolderImage()
                self.recorder.log_action("nextImage")
            else:
                QApplication.beep()   # 已達最後一張時發聲
                self.statusBar().showMessage(tr("已是最後一張"))
            self.auto_process_panel.update_loop_button_state()
        finally:
            self._navigating = False

    def prevImage(self):
        # 防止重入（例如快捷鍵與 QAction 同時觸發）
        if getattr(self, "_navigating", False):
            return
        self._navigating = True
        try:
            # 跨頁循環模式下僅更新索引並載入新圖（不觸發其他 UI 更新）
            if self.inLoopMode:
                if self.currentImageIndex > 0:
                    self.currentImageIndex -= 1
                    self.loadCurrentFolderImage()
                return
            if not self.folderImages:
                QApplication.beep()   # 無文件夾時發聲
                self.statusBar().showMessage(tr("請先導入文件夾"))
                return
            if not self.confirmDiscardSlices():
                return
            if self.currentImageIndex > 0:
                self.currentImageIndex -= 1
                self.loadCurrentFolderImage()
                self.recorder.log_action("prevImage")
            else:
                QApplication.beep()   # 已達第一張時發聲
                self.statusBar().showMessage(tr("已是第一張"))
            self.auto_process_panel.update_loop_button_state()
        finally:
            self._navigating = False

    def loadImagePath(self, path: str) -> None:
        if not path or not os.path.isfile(path):
            return
        # 載入前先清空列表並抑制預覽更新
        self._suppressPreviewUpdate = True
        self.sliceList.clear()
        self.sliceView.loadImage(path)
        filename = os.path.basename(path)
        self.statusBar().showMessage(tr('載入圖片：{0}').format(filename))
        self.originalBaseName = os.path.splitext(filename)[0]
        self.currentImagePath = path  # 儲存圖片路徑
        # 匯入單張圖片時，清除先前的資料夾上下文（避免仍在文件夾翻頁）
        try:
            self.currentFolder = ""
            self.folderImages = []
            self.currentImageIndex = -1
        except Exception:
            pass

        # 更新跳轉控件（若存在）以反映單圖狀態
        try:
            if hasattr(self, 'imageJumpSpin'):
                self.imageJumpSpin.setMaximum(1)
                self.imageJumpSpin.setValue(1)
            if hasattr(self, 'imageTotalLabel'):
                self.imageTotalLabel.setText("/1")
        except Exception:
            pass

        self.checkAndLoadProject()     # 自動檢査工程文件
        # 恢復預覽更新並刷新一次
        self._suppressPreviewUpdate = False
        try:
            self.update_preview_panel()
        except Exception:
            pass
        self.auto_process_panel.update_loop_button_state()
        self.sliceView.viewport().update()

    def openImage(self):
        filters = "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)"
        path, _ = QFileDialog.getOpenFileName(self, tr("導入圖片"), "", filters)
        if path:
            self.loadImagePath(path)


    def checkAndLoadProject(self):
        if self.currentImagePath:
            # 預設為未載入工程，後續若成功載入會設為 True
            self._project_loaded = False
            directory = os.path.dirname(self.currentImagePath)
            base = os.path.splitext(os.path.basename(self.currentImagePath))[0]
            proj_path = os.path.join(directory, base + ".cutter")
            
            # 如果存在同名工程文件，優先加載
            if os.path.exists(proj_path):
                self.loadProjectFile(proj_path, tr('自動載入工程文件：{0}').format(os.path.basename(proj_path)))
                self._project_loaded = True
            # 如果不存在同名工程文件，但有預設工程，則加載預設工程
            elif self.defaultProjectPath and os.path.exists(self.defaultProjectPath):
                self.loadProjectFile(self.defaultProjectPath, tr('載入預設工程：{0}').format(os.path.basename(self.defaultProjectPath)))
                self._project_loaded = True
            
            json_path = os.path.splitext(self.currentImagePath)[0] + ".json"
            cutter_path = os.path.splitext(self.currentImagePath)[0] + ".cutter"
            if os.path.exists(json_path) and not os.path.exists(cutter_path):
                # 自動對其進行第1513行至第1595行的操作
                self.importKandianJson(json_path)

            # 若沒有任何工程被載入，且目前切片列表為空，則視為無改動狀態
            if not self._project_loaded:
                has_slices = any(isinstance(it, SliceRect) for it in self.sliceView.scene().items())
                if not has_slices:
                    try:
                        self._last_saved_project_data = ""
                    except Exception:
                        pass
                    try:
                        self.clearProjectEdited()
                    except Exception:
                        pass

    def loadProjectFile(self, proj_path, status_message):
        # 先清空列表並抑制預覽更新，避免在移除場景項時觸發預覽讀取已刪除物件
        try:
            self._suppressPreviewUpdate = True
            self.sliceList.clear()
        except Exception:
            pass
        # 再移除現有切片（保留圖片項）
        for item in self.sliceView.scene().items():
            if isinstance(item, SliceRect):
                self.sliceView.scene().removeItem(item)
        with open(proj_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, l in enumerate(lines):
                parts = l.strip().split("\t")
                if len(parts) >= 5:  # 確保有足夠的數據
                    try:
                        x, y, w, h = map(float, parts[:4])
                        name = parts[4]
                        new_slice = SliceRect(QRectF(x, y, w, h), i+1, name=name)
                        self.sliceView.scene().addItem(new_slice)
                    except ValueError:
                        self.statusBar().showMessage(tr('無效數據在行 {0}: {1}').format(i + 1, l.strip()))
                elif len(parts) == 4: # 向下兼容
                    try:
                        x, y, w, h = map(float, parts[:4])
                        new_slice = SliceRect(QRectF(x, y, w, h), i+1)
                        self.sliceView.scene().addItem(new_slice)
                    except ValueError:
                        self.statusBar().showMessage(tr('無效數據在行 {0}: {1}').format(i + 1, l.strip()))
        self.updateSliceList()
        self.statusBar().showMessage(status_message)
        # 載入工程後，刷新快照並清除已編輯狀態，避免未改動時翻頁彈出保存提示
        try:
            self._last_saved_project_data = self.getCurrentProjectData()
        except Exception:
            self._last_saved_project_data = ""
        try:
            self.clearProjectEdited()
        except Exception:
            pass
        # 設定旗標：已載入工程
        self._project_loaded = True
        # 恢復預覽更新並刷新一次
        self._suppressPreviewUpdate = False
        try:
            self.update_preview_panel()
        except Exception:
            pass

    def writeProjectFile(self, file_path):
        slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        slices.sort(key=lambda s: s.number)
        # 改成 5 個欄位：X Y 寬 高 名稱（即使名稱為空）
        projectData = "\n".join([
            "\t".join([
                str(int(item.rect().x())),
                str(int(item.rect().y())),
                str(int(item.rect().width())),
                str(int(item.rect().height())),
                item.name  # 可能為空
            ]) for item in slices
        ])
        if not projectData.strip():
            if os.path.exists(file_path):
                os.remove(file_path)
            self.statusBar().showMessage(tr("工程已保存：無切片數據，空工程文件已刪除"))
            # 更新快照：空內容表示無切片
            try:
                self._last_saved_project_data = ""
            except Exception:
                pass
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(projectData)
            self.statusBar().showMessage(tr('工程已保存：{0}').format(file_path))
            # 更新快照為當前內容
            try:
                self._last_saved_project_data = projectData
            except Exception:
                pass

    def saveProject(self):
        if not self.currentImagePath:
            self.statusBar().showMessage(tr("請先導入圖片"))
            return
        directory = os.path.dirname(self.currentImagePath)
        base = os.path.splitext(os.path.basename(self.currentImagePath))[0]
        file_path = os.path.join(directory, base + ".cutter")
        try:
            self.writeProjectFile(file_path)
            # 成功寫入後清除已編輯標記
            self.clearProjectEdited()
            # 如果沒有特殊情況，更新最後保存快照（writeProjectFile 也會更新）
        except Exception as e:
            QMessageBox.warning(self, tr("錯誤"), tr('保存失敗：{0}').format(e))
            return
        try:
            self.recorder.log_action("saveProject")
        except Exception:
            pass

    def saveProjectAs(self):
        if not self.currentImagePath:
            self.statusBar().showMessage(tr("請先導入圖片"))
            return
        directory = os.path.dirname(self.currentImagePath)
        base = os.path.splitext(os.path.basename(self.currentImagePath))[0]
        default_name = base + ".cutter"
        file_path, _ = QFileDialog.getSaveFileName(self, tr("工程另存爲"), os.path.join(directory, default_name), tr("工程文件 (*.cutter)"))
        if file_path:
            if not file_path.endswith(".cutter"):
                file_path += ".cutter"
            try:
                self.writeProjectFile(file_path)
                self.clearProjectEdited()
            except Exception as e:
                QMessageBox.warning(self, tr("錯誤"), tr('另存為失敗：{0}').format(e))
                return

    def exportSlices(self):
        if not self.sliceView.image_item:
            self.statusBar().showMessage(tr("請先導入圖片"))
            return
        # 判斷是否為脚本自動執行（即 recorder 正在錄製時為手動）
        is_script_mode = getattr(self, "is_script_running", False)
        # 若有預設導出目錄與格式，則直接使用
        if self.defaultExportDir and self.defaultExportFormat:
            export_dir = self.defaultExportDir
            fmt = self.defaultExportFormat
        elif is_script_mode:
            # 脚本自動執行時，未設置預設則跳過
            self.statusBar().showMessage(tr("脚本執行：未設置導出預設，導出切片已跳過"))
            return
        else:
            # 手動操作時，彈出選擇目錄與格式
            export_dir = QFileDialog.getExistingDirectory(self, tr("選擇導出目錄"), "")
            if not export_dir:
                return
            formats = ["PNG", "JPG", "BMP"]
            fmt, ok = QInputDialog.getItem(self, tr("選擇格式"), tr("導出格式:"), formats, 0, False)
            if not ok:
                return
        original = self.sliceView.image_item.pixmap().toImage()
        base = getattr(self, "originalBaseName", "IMAGE")
        slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        slices.sort(key=lambda s: s.number)
        for idx, item in enumerate(slices, start=1):
            rect = item.rect().toRect()
            cropped = original.copy(rect)
            if item.name:
                file_name = f"{base}_{idx:03d}_{item.name}.{fmt.lower()}"
            else:
                file_name = f"{base}_{idx:03d}.{fmt.lower()}"
            file_path = os.path.join(export_dir, file_name)
            cropped.save(file_path, fmt)
        QApplication.beep()
        self.statusBar().showMessage(tr('導出完成, 輸出目錄：{0}').format(export_dir))
        # 錄製脚本
        if hasattr(self.recorder, "is_recording") and self.recorder.is_recording:
            self.recorder.log_action("exportSlices")

    def showAbout(self):
        QMessageBox.about(self, tr("關於"), tr("囫圇切 HulenCut v0.8.0\n\nhttps://vistudium.top/gouken/\n\n鳴謝：\nGithub Copilot\nDeepSeek Harness\nBasic 低手\n南池子\nKushim Jiang\n\n活字攷古 @hulenkius 絶讚狗啃中"))
        
    def showManual(self):
        manual_text = (
            tr("左鍵拖拽創建切片，雙擊選擇切片，或在列表中選擇。\n"
            "對着手柄雙擊後按住左鍵拖拽以調整切片邊緣。\n"
            "按住 Ctrl 在視圖中進行 單擊/拖拽 以多選。\n"
            "雙擊後按住左鍵拖拽移動切片，也可用方向鍵移動。\n"
            "右鍵切片以刪除，或在列表中 右鍵/Delete 鍵刪除。\n"
            "當指定了切片固定寬高時不支持雙擊操作。\n"
            "\n自動處理工具支持自動識別、移動、縮放、篩除、\n規整化、合併重疊、校正拉直、上一張、下一張、\n保存工程、導出切片、清空切片名稱。不支持創建切片、\n重命名、劃分切片、調整切片順序、裁剪圖片。\n"
            "\n觀看教程影片以獲得更多幫助。")
        )
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("操作指南"))
        layout = QVBoxLayout(dialog)
        
        lblManual = QLabel(manual_text, dialog)
        lblManual.setWordWrap(True)
        layout.addWidget(lblManual)
        
        # 底部按鈕區，參考檢査更新對話框排版
        btnLayout = QHBoxLayout()
        btnTutorial = QPushButton(tr("教程影片"), dialog)
        btnTutorial.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://space.bilibili.com/66758675/lists/4816821")))
        btnLayout.addWidget(btnTutorial)
        
        btnOk = QPushButton(tr("確定"), dialog)
        btnOk.clicked.connect(dialog.accept)
        btnLayout.addWidget(btnOk)
        
        layout.addLayout(btnLayout)
        dialog.exec_()

    def openProjectPath(self, path: str) -> None:
        if not path or not os.path.isfile(path):
            return
        # 與自動載入路徑保持一致，統一交由 loadProjectFile 處理
        try:
            self.loadProjectFile(path, tr('已載入工程：{0}').format(os.path.basename(path)))
        except Exception as e:
            QMessageBox.warning(self, tr("錯誤"), tr('工程載入失敗：{0}').format(e))

    def openProject(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("導入工程"), "", tr("工程文件 (*.cutter)"))
        if path:
            self.openProjectPath(path)

    # 清空切片的槽函數
    def clearAllSlices(self):
        scene = self.sliceView.scene()
        for item in scene.items():
            if isinstance(item, SliceRect):
                scene.removeItem(item)
        self.updateSliceList()
        QApplication.beep()
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage(tr("所有切片已清空"))
        if hasattr(self, "markProjectEdited"):
            self.markProjectEdited()

    # 移動切片功能
    def openMoveSlicesDialog(self):
        dlg = MoveSlicesDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            target, dx, dy = dlg.getValues()
            self.recorder.log_action("moveSlices", target, dx, dy)
            if target == "all":
                slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
            else:
                slices = []
                for listItem in self.sliceList.selectedItems():
                    s = listItem.data(Qt.UserRole)
                    if s:
                        slices.append(s)
            for s in slices:
                s.setRect(s.rect().translated(dx, dy))
            self.updateSliceList()
            self.statusBar().showMessage(tr("切片移動完成"))
            self.markProjectEdited()

    # 縮放切片功能
    def openScaleSlicesDialog(self):
        dlg = ScaleSlicesDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            target, scaleX, scaleY = dlg.getValues()
            self.recorder.log_action("scaleSlices", target, scaleX, scaleY)
            if target == "all":
                slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
            else:
                slices = []
                for listItem in self.sliceList.selectedItems():
                    s = listItem.data(Qt.UserRole)
                    if s:
                        slices.append(s)
            for s in slices:
                rect = s.rect()
                cx = rect.x() + rect.width()/2
                cy = rect.y() + rect.height()/2
                new_w = rect.width() * (scaleX/100.0)
                new_h = rect.height() * (scaleY/100.0)
                new_rect = QRectF(cx - new_w/2, cy - new_h/2, new_w, new_h)
                s.setRect(new_rect)
            self.updateSliceList()
            self.statusBar().showMessage(tr("切片縮放完成"))
            self.markProjectEdited()

    def openScaleProjectDialog(self):
        dlg = ScaleProjectDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            scale_factor = dlg.getScaleFactor()
            # 獲取所有切片
            slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
            if not slices:
                self.statusBar().showMessage(tr("沒有切片可以縮放"))
                return
            
            # 縮放所有切片的座標
            for s in slices:
                rect = s.rect()
                # 將座標乘以係數，並四捨五入到整數
                new_x = round(rect.x() * scale_factor)
                new_y = round(rect.y() * scale_factor)
                new_w = round(rect.width() * scale_factor)
                new_h = round(rect.height() * scale_factor)
                new_rect = QRectF(new_x, new_y, new_w, new_h)
                s.setRect(new_rect)
            
            self.updateSliceList()
            self.statusBar().showMessage(tr('工程座標縮放完成（係數：{0}）').format(scale_factor))
            self.markProjectEdited()
            
            # 記錄腳本動作
            self.recorder.log_action("scaleProject", scale_factor)

    def importKandianJson(self, jsonFilePath=None):
        # 檢査是否有當前圖片
        if not self.currentImagePath:
            QApplication.beep()
            self.statusBar().showMessage(tr("請先導入圖片"))
            return
    
        # 若未提供路徑則由使用者選擇 json
        if not jsonFilePath:
            jsonFilePath, _ = QFileDialog.getOpenFileName(self, tr("選擇看典古籍json"), "", tr("JSON 文件 (*.json)"))
            if not jsonFilePath:
                return
    
        # 讀取 json 並轉換
        try:
            with open(jsonFilePath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.statusBar().showMessage(tr('錯誤：讀取json失敗：{0}').format(e))
            return
    
        # 定義輔助函數：根據 pts 資料計算矩形
        def computeRect(pts):
            if pts and isinstance(pts[0], (int, float)):
                if len(pts) >= 4:
                    x, y, x2, y2 = pts[:4]
                    return x, y, x2 - x, y2 - y
                return None
            else:
                xs = [pt[0] for pt in pts if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                ys = [pt[1] for pt in pts if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                if xs and ys:
                    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
            return None
    
        slices = []
        slice_index = 0
        # 對於每一行，計算外接矩形，並進一步劃分爲多個切片（如果有 "words" 的位置信息）
        for line in data.get("text_lines", []):
            # 若存在 words 且有有效資料，嘗試逐個 word 劃分
            if "words" in line and line["words"]:
                has_valid = False
                for word in line["words"]:
                    pts = word.get("position", [])
                    rect = computeRect(pts)
                    name = word.get("text", "")
                    if rect:
                        slices.append({
                            "number": slice_index,
                            "rect": list(rect),
                            "name": name
                        })
                        slice_index += 1
                        has_valid = True
                # 若 words 資料存在但均無位置信息，則退回使用整行信息
                if has_valid:
                    continue
            # 使用整行的 position 數據
            pts = line.get("position", [])
            rect = computeRect(pts)
            if rect:
                # 使用整行的 text 作為名稱
                name = line.get("text", "")
                slices.append({
                    "number": slice_index,
                    "rect": list(rect),
                    "name": name
                })
                slice_index += 1
    
        # 按當前圖片與 json 標註尺寸比，縮放所有切片坐標
        if self.sliceView.image_item:
            pix = self.sliceView.image_item.pixmap()
            actual_w, actual_h = pix.width(), pix.height()
            json_w = data.get("width", actual_w)
            json_h = data.get("height", actual_h)
            if json_w and json_h:
                ratio_x = actual_w / json_w
                ratio_y = actual_h / json_h
                for s in slices:
                    x, y, w, h = s["rect"]
                    s["rect"] = [
                        x * ratio_x,
                        y * ratio_y,
                        w * ratio_x,
                        h * ratio_y
                    ]

        # 應用json導入預設：位置偏移與（若勾選）切片篩除
        new_slices = []
        if self.jsonImportPreset is not None:
            preset = self.jsonImportPreset
            offset_x = preset["offset_x"]
            offset_y = preset["offset_y"]
            filtering = preset.get("filtering", False)
            
            # 篩除邏輯函數
            def checkCondition(slice_rect, condition):
                x, y, w, h = slice_rect
                dim, op, val = condition["dimension"], condition["operator"], condition["value"]
                
                if dim == "w":
                    size = w
                elif dim == "h":
                    size = h
                else:
                    return False
                
                if op == "greater":
                    return size > val
                elif op == "equal":
                    return size == val
                elif op == "less":
                    return size < val
                return False
            
            for s in slices:
                x, y, w, h = s["rect"]
                x += offset_x
                y += offset_y
                s["rect"] = [x, y, w, h]
                
                # 如果啟用篩選，進行篩選檢査
                if filtering:
                    condition1 = preset.get("condition1")
                    logic = preset.get("logic")
                    condition2 = preset.get("condition2")
                    
                    should_remove = False
                    
                    if condition1:
                        # 檢査第一個條件
                        condition1_result = checkCondition(s["rect"], condition1)
                        
                        if logic is None:
                            # 只有一個條件
                            should_remove = condition1_result
                        else:
                            # 有兩個條件
                            if condition2:
                                condition2_result = checkCondition(s["rect"], condition2)
                                
                                # 處理相同維度的特殊情況
                                if condition1["dimension"] == condition2["dimension"]:  # 相同維度
                                    # 構成數學集合條件
                                    if logic == "or":
                                        should_remove = condition1_result or condition2_result
                                    elif logic == "and":
                                        should_remove = condition1_result and condition2_result
                                else:
                                    # 不同維度
                                    if logic == "or":
                                        should_remove = condition1_result or condition2_result
                                    elif logic == "and":
                                        should_remove = condition1_result and condition2_result
                    
                    # 如果不需要移除，則添加到新列表
                    if not should_remove:
                        new_slices.append(s)
                else:
                    # 不篩選，直接添加
                    new_slices.append(s)
        else:
            new_slices = slices

        # 生成同名的 .cutter 工程文件
        cutterfn = os.path.splitext(jsonFilePath)[0] + ".cutter"
        project = {
            "image": self.currentImagePath,
            "slices": new_slices
        }
        try:
            with open(cutterfn, 'w', encoding='utf-8') as f:
                json.dump(project, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.statusBar().showMessage(tr('錯誤：寫入工程文件失敗：{0}').format(e))
            return
    
        # 清空現有切片（保留圖片項）
        scene = self.sliceView.scene()
        for item in list(scene.items()):
            if isinstance(item, SliceRect):
                scene.removeItem(item)
    
        # 根據轉換後數據新增切片
        for s in new_slices:
            rect_values = s["rect"]
            new_slice = SliceRect(QRectF(*rect_values), s["number"], name=s.get("name", ""))
            scene.addItem(new_slice)
    
        # 在顯示成功導入訊息前，覆寫當前切片列表工程至 cutterfn 文件
        self.writeProjectFile(cutterfn)
        
        self.updateSliceList()
        self.statusBar().showMessage(tr('成功轉換並導入工程文件：{0}').format(cutterfn))
        self.markProjectEdited()

    # 篩除切片功能
    def filterSlices(self):
        dlg = FilterSlicesDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            target, condition1, logic, condition2 = dlg.getValues()
            
            # 構建腳本記錄命令
            cmd_parts = ["filterSlices", target]
            cmd_parts.append(f"[{condition1[0]},{condition1[1]},{condition1[2]}]")
            if logic and condition2:
                cmd_parts.append(logic)
                cmd_parts.append(f"[{condition2[0]},{condition2[1]},{condition2[2]}]")
            self.recorder.log_action(*cmd_parts)
            
            # 選定要處理的切片
            if target == "all":
                slices = [s for s in self.sliceView.scene().items() if isinstance(s, SliceRect)]
            else:
                slices = [s for s in self.sliceList.selectedItems() if s.data(Qt.UserRole)]
                slices = [s.data(Qt.UserRole) for s in slices]
            
            # 篩除邏輯函數
            def checkCondition(slice_rect, condition):
                w = slice_rect.rect().width()
                h = slice_rect.rect().height()
                dim, op, val = condition
                
                if dim == "w":
                    size = w
                elif dim == "h":
                    size = h
                else:
                    return False
                
                if op == "greater":
                    return size > val
                elif op == "equal":
                    return size == val
                elif op == "less":
                    return size < val
                return False
            
            # 根據條件移除切片
            for s in slices:
                should_remove = False
                
                # 檢査第一個條件
                condition1_result = checkCondition(s, condition1)
                
                if logic is None:
                    # 只有一個條件
                    should_remove = condition1_result
                else:
                    # 有兩個條件
                    condition2_result = checkCondition(s, condition2)
                    
                    # 處理相同維度的特殊情況
                    if condition1[0] == condition2[0]:  # 相同維度
                        # 構成數學集合條件
                        if logic == "or":
                            should_remove = condition1_result or condition2_result
                        elif logic == "and":
                            should_remove = condition1_result and condition2_result
                    else:
                        # 不同維度
                        if logic == "or":
                            should_remove = condition1_result or condition2_result
                        elif logic == "and":
                            should_remove = condition1_result and condition2_result
                
                if should_remove:
                    self.sliceView.scene().removeItem(s)
            
            self.updateSliceList()
            self.statusBar().showMessage(tr("切片篩除完成"))
            self.markProjectEdited()

    # 打開劃分切片對話框
    def openDivideSlicesDialog(self):
        # 檢査是否處於裁剪或校正模式
        if self.croppingMode or self.straighteningMode:
            self.statusBar().showMessage(tr("裁剪或校正模式下無法執行劃分切片！"))
            return
        # 若正在錄製脚本，彈窗警告
        if self.recorder.is_recording:
            QMessageBox.warning(self, tr("警告"), tr("自動處理無法應用於劃分切片！"))
            return
        dialog = DivideSlicesDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            cols, rows, method = dialog.getValues()
            self.divide_params = (cols, rows, method)
            self.dividingSlices = True
            self.dividePoints = []
            self.statusBar().showMessage(tr("劃分切片：請點選第一個點"))

    # 處理劃分切片
    def divideSlices(self):
        if not self.divide_params or len(self.dividePoints) < 2:
            return
        cols, rows, method = self.divide_params
        p1, p2 = self.dividePoints[0], self.dividePoints[1]
        scene = self.sliceView.scene()
        items = []
        if (method == "corner"):
            x1, y1 = min(p1.x(), p2.x()), min(p1.y(), p2.y())
            x2, y2 = max(p1.x(), p2.x()), max(p1.y(), p2.y())
            total_width = x2 - x1
            total_height = y2 - y1
            cell_w = total_width / cols
            cell_h = total_height / rows
            for r in range(rows):
                for c in range(cols):
                    rect = QRectF(x1 + c * cell_w, y1 + r * cell_h, cell_w, cell_h)
                    slice_number = len([it for it in scene.items() if isinstance(it, SliceRect)]) + 1
                    new_slice = SliceRect(rect, slice_number)
                    scene.addItem(new_slice)
                    items.append(new_slice)
        else:  # 置中方法
            x1, y1 = min(p1.x(), p2.x()), min(p1.y(), p2.y())
            x2, y2 = max(p1.x(), p2.x()), max(p1.y(), p2.y())
            total_width = x2 - x1
            total_height = y2 - y1
            cell_w = total_width / (cols - 1) if cols > 1 else total_width
            cell_h = total_height / (rows - 1) if rows > 1 else total_height
            for r in range(rows):
                for c in range(cols):
                    center_x = x1 + c * cell_w
                    center_y = y1 + r * cell_h
                    rect = QRectF(center_x - cell_w/2, center_y - cell_h/2, cell_w, cell_h)
                    slice_number = len([it for it in scene.items() if isinstance(it, SliceRect)]) + 1
                    new_slice = SliceRect(rect, slice_number)
                    scene.addItem(new_slice)
                    items.append(new_slice)
        scene.clearSelection()
        for s in items:
            s.setSelected(True)
        self.updateSliceList()
        self.statusBar().showMessage(tr("劃分切片完成"))
        if hasattr(self, "markProjectEdited"):
            self.markProjectEdited()

    # 檢査更新功能
    def checkUpdate(self):
        checkingDlg = QDialog(self)
        checkingDlg.setWindowTitle(tr("檢査更新"))
        checkingDlg.setWindowModality(Qt.NonModal)
        layout = QVBoxLayout(checkingDlg)
        layout.addWidget(QLabel(tr("⌛️正在檢査更新，請稍候……\n若窗口長時間無響應，請關閉程序。"), checkingDlg))
        checkingDlg.show()
        QApplication.processEvents()
        try:
            response = urllib.request.urlopen("https://vistudium.top/gouken/UPDATE")
            update_text = response.read().decode("utf-8")
        except Exception as e:
            update_text = tr("無法取得更新資訊：") + str(e)
        checkingDlg.close()
        dlg = CheckUpdateDialog(self.currentVersion, self, update_text=update_text)
        dlg.exec_()

    # 新增標記方法與狀態指示更新
    def markProjectEdited(self):
        try:
            current_data = self.getCurrentProjectData()
        except Exception:
            # 若無法取得快照，保守起見仍視為未修改變更狀態不變
            current_data = None
        if current_data is not None:
            # 嚴格比對當前快照與保存快照
            self.projectEdited = (current_data != getattr(self, "_last_saved_project_data", ""))
        else:
            # 無法比對時，不主動置 True，維持現狀
            pass
        # 更新指示器
        if hasattr(self, "updateModifiedIndicator"):
            self.updateModifiedIndicator()

    def clearProjectEdited(self):
        self.projectEdited = False
        # 更新指示器
        if hasattr(self, "updateModifiedIndicator"):
            self.updateModifiedIndicator()

    def updateModifiedIndicator(self):
        # 根據 projectEdited 顯示右側狀態
        if not hasattr(self, "modifiedIndicator") or self.modifiedIndicator is None:
            return
        if getattr(self, "projectEdited", False):
            self.modifiedIndicator.setText(tr("❗️有改動未保存"))
            self.modifiedIndicator.setStyleSheet("color:#d32f2f; padding-left:8px;")
        else:
            self.modifiedIndicator.setText(tr("✔️當前無需保存"))
            self.modifiedIndicator.setStyleSheet("color:#2e7d32; padding-left:8px;")

    # 规整化切片動作，依據切片中心點更新指定寬高
    def openNormalizeSlicesDialog(self):
        dialog = NormalizeSlicesDialog(self)
        if dialog.exec_():
            target, new_width, new_height = dialog.getValues()
            # 根據目標取得切片列表
            if target == "all":
                slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
            else:
                slices = self.sliceView.scene().selectedItems()
            count = 0
            for s in slices:
                if isinstance(s, SliceRect):
                    center = s.rect().center()
                    current_rect = s.rect()
                    # 只修改勾選的維度，未勾選的維度保持原值
                    width = new_width if new_width is not None else current_rect.width()
                    height = new_height if new_height is not None else current_rect.height()
                    new_rect = QRectF(center.x() - width/2, center.y() - height/2, width, height)
                    s.setRect(new_rect)
                    s.updateHandles()
                    count += 1
            self.updateSliceList()
            if hasattr(self, "statusBar"):
                self.statusBar().showMessage(tr('切片規整化完成，已處理 {0} 個切片').format(count))
            if hasattr(self, "markProjectEdited"):
                self.markProjectEdited()
            # 記錄腳本操作
            if hasattr(self, "recorder") and self.recorder.is_recording:
                width_param = new_width if new_width is not None else "null"
                height_param = new_height if new_height is not None else "null"
                self.recorder.log_action("normalizeSlices", target, width_param, height_param)

    # 辨識定位相關功能
    def autoRecognizeWordSlices(self):
        if not self.sliceView.image_item:
            return
        # 選擇圖片風格對話框
        styles = ("白底黑字", "黑底白字")
        display_styles = [tr(style) for style in styles]
        display_style, ok = QInputDialog.getItem(
            self,
            tr("選擇圖片風格"),
            tr("請選擇圖片風格："),
            display_styles,
            0,
            False,
        )
        if not ok:
            return
        style = i18n.to_source(display_style)
        self.recorder.log_action("autoRecognize", style)
        qimg = self.sliceView.image_item.pixmap().toImage()
        width, height = qimg.width(), qimg.height()
        ptr = qimg.bits()
        ptr.setsize(qimg.byteCount())
        img_array = np.array(ptr).reshape(height, width, 4)
        gray = cvtColor(img_array, COLOR_BGRA2GRAY)
        # 根據用戶選擇的圖片風格應用不同二值化方式
        if style == "白底黑字":
            _, thresh = threshold(gray, 127, 255, THRESH_BINARY_INV)
        else:
            _, thresh = threshold(gray, 127, 255, THRESH_BINARY)
        # 輪廓檢測
        contours, _ = findContours(thresh, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)
        rects = []
        for cnt in contours:
            x, y, w, h = boundingRect(cnt)
            rects.append(QRectF(x, y, w, h))
        for rect in rects:
            new_slice = SliceRect(rect, number=0)  # 編號後續於 updateSliceList 中更新
            self.sliceView.scene().addItem(new_slice)
        self.updateSliceList()
        QApplication.beep()
        self.statusBar().showMessage(tr('自動識別完成，新增 {0} 切片').format(len(rects)))
        self.markProjectEdited()

    # 自動識別表格功能
    def autoDetectTable(self):
        if not self.sliceView.image_item:
            self.statusBar().showMessage(tr("請先導入圖片"))
            return
            
        dlg = TableDetectDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
            
        params = dlg.getValues()
        self.recorder.log_action("detectTable", 
                               params["style"],
                               params["min_width"],
                               params["min_height"],
                               f"{params['threshold']:.2f}")
        
        # 獲取圖像數據
        qimg = self.sliceView.image_item.pixmap().toImage()
        width, height = qimg.width(), qimg.height()
        ptr = qimg.bits()
        ptr.setsize(qimg.byteCount())
        img_array = np.array(ptr).reshape(height, width, 4)
        
        # 轉換為灰度圖
        gray = cvtColor(img_array, COLOR_BGRA2GRAY)
        
        # 根據風格選擇進行二值化
        if params["style"] == "白底黑字":
            _, binary = threshold(gray, 127, 255, THRESH_BINARY_INV)
        else:
            _, binary = threshold(gray, 127, 255, THRESH_BINARY)
        
        # 計算投影
        h_proj = np.sum(binary, axis=1)
        v_proj = np.sum(binary, axis=0)
        
        # 尋找峰值
        def find_peaks(proj, threshold):
            peaks = []
            max_val = np.max(proj)
            for i in range(1, len(proj) - 1):
                if (proj[i-1] < proj[i] and proj[i+1] < proj[i] and 
                    proj[i] > threshold * max_val):
                    peaks.append(i)
            return peaks
        
        # 獲取橫線和豎線位置
        h_lines = find_peaks(h_proj, params["threshold"])
        v_lines = find_peaks(v_proj, params["threshold"])
        
        # 清空現有切片
        for item in self.sliceView.scene().items():
            if isinstance(item, SliceRect):
                self.sliceView.scene().removeItem(item)
        
        # 根據檢測結果創建切片
        slice_count = 0
        for i in range(len(h_lines) - 1):
            for j in range(len(v_lines) - 1):
                y1, y2 = h_lines[i], h_lines[i + 1]
                x1, x2 = v_lines[j], v_lines[j + 1]
                
                # 檢査尺寸是否滿足最小要求
                w = x2 - x1
                h = y2 - y1
                if w >= params["min_width"] and h >= params["min_height"]:
                    rect = QRectF(x1, y1, w, h)
                    new_slice = SliceRect(rect, slice_count + 1)
                    self.sliceView.scene().addItem(new_slice)
                    slice_count += 1
        
        self.updateSliceList()
        QApplication.beep()
        self.statusBar().showMessage(tr('表格識別完成，共新增 {0} 個切片').format(slice_count))
        self.markProjectEdited()

    def mergeOverlappingSlices(self):
        # 檢査是否處於裁剪或校正模式
        if self.croppingMode or self.straighteningMode:
            self.statusBar().showMessage(tr("裁剪或校正模式下無法執行合併重疊切片！"))
            return
        scope, ok = QInputDialog.getItem(self, tr("合併重疊切片"), tr("選擇切片範圍："), [tr("全部"), tr("已選擇")], 0, False)
        if not ok:
            return
        self.recorder.log_action("mergeOverlapping", "all" if scope == tr("全部") else "selected")
        if scope == tr("已選擇"):
            slices = [item for item in self.sliceView.scene().selectedItems() if isinstance(item, SliceRect)]
        else:
            slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        if not slices:
            QMessageBox.information(self, tr("合併重疊切片"), tr("沒有可處理的切片"))
            return
        n = len(slices)
        # 預先取得各切片的矩形
        rects = [s.rect() for s in slices]
        visited = [False] * n
        groups = []
        def overlaps(r1, r2):
            return r1.intersects(r2)
        for i in range(n):
            if visited[i]:
                continue
            group = [i]
            stack = [i]
            visited[i] = True
            while stack:
                cur = stack.pop()
                for j in range(n):
                    if not visited[j] and overlaps(rects[cur], rects[j]):
                        # 簡單檢査：若與組內任一切片相交則加入同一組
                        if any(overlaps(rects[k], rects[j]) for k in group):
                            visited[j] = True
                            stack.append(j)
                            group.append(j)
            if len(group) > 1:
                groups.append(group)
        # 對每一組合併，並替換原有切片
        for group in groups:
            union_rect = rects[group[0]]
            for idx in group[1:]:
                union_rect = union_rect.united(rects[idx])
            # 刪除原切片（由後往前刪除避免索引問題）
            for idx in sorted(group, reverse=True):
                self.sliceView.scene().removeItem(slices[idx])
            new_slice = SliceRect(union_rect, number=0)
            self.sliceView.scene().addItem(new_slice)
        self.updateSliceList()
        self.statusBar().showMessage(tr("合併重疊切片完成"))
        self.markProjectEdited()

    def jumpToImage(self):
        # 根據用戶輸入跳轉圖片（索引從 1 開始）
        target = self.imageJumpSpin.value() - 1
        if self.folderImages and 0 <= target < len(self.folderImages):
            if target != self.currentImageIndex:
                self.currentImageIndex = target
                self.loadCurrentFolderImage()

    # 批量重命名方法
    def openBatchRenameDialog(self):
        # 檢査是否處於裁剪或校正模式
        if self.croppingMode or self.straighteningMode:
            self.statusBar().showMessage(tr("裁剪或校正模式下無法執行批量重命名！"))
            return
        dlg = BatchRenameDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            lines = dlg.getRenameLines()
            if not lines:
                self.statusBar().showMessage(tr("無有效重命名內容"))
                return
            count = self.sliceList.count()
            for i in range(min(len(lines), count)):
                item = self.sliceList.item(i)
                slice_item = item.data(Qt.UserRole)
                if slice_item:
                    slice_item.name = lines[i]
            self.updateSliceList()
            self.statusBar().showMessage(tr("批量重命名完成"))
            if hasattr(self, "markProjectEdited"):
                self.markProjectEdited()

    # 清空切片名稱功能
    def clearAllSliceNames(self):
        for i in range(self.sliceList.count()):
            item = self.sliceList.item(i)
            slice_item = item.data(Qt.UserRole)
            if slice_item:
                slice_item.name = ""
        self.updateSliceList()
        self.statusBar().showMessage(tr("已清空全部切片名稱"))
        self.markProjectEdited()
        if hasattr(self, "recorder") and self.recorder.is_recording:
            self.recorder.log_action("clearSliceNames")

    # 圖片校正處理
    def straightenImage(self, p1, p2):
        x1,y1 = p1.x(), p1.y()
        x2,y2 = p2.x(), p2.y()
        if x1==x2 or y1==y2:
            self.statusBar().showMessage(tr("兩點在同一水平/垂直線上，無法校正"))
            return
        src = self.currentImagePath
        # 計算斜率與角度
        k = (y2 - y1) / (x2 - x1)
        theta = math.degrees(abs(math.atan(k)))
        if 0 < k < 1:  # 已檢驗
            angle = - theta 
        elif -1 < k < 0:  # 已檢驗
            angle = theta
        elif k > 1:  # 已檢驗
            angle = 90 - theta
        else:  # k < -1  已檢驗
            angle = theta - 90
        # 讀取、旋轉、覆寫原圖
        img = QImage(src)
        tr = QTransform().rotate(angle)
        rot = img.transformed(tr, Qt.SmoothTransformation)
        rot.save(src)
        # 重新載入到視圖
        self.sliceView.loadImage(src)

    # 直線校正流程方法
    def hasSlices(self):
        return any(isinstance(it, SliceRect) for it in self.sliceView.scene().items())

    def startStraightenMode(self):
        # 不可在裁剪模式下啓動校正
        if self.croppingMode:
            QApplication.beep()
            self.statusBar().showMessage(tr("裁剪模式激活中，無法進入校正模式"))
            return
        if not self.sliceView.image_item:
            self.statusBar().showMessage(tr("請先導入圖片")); QApplication.beep(); return
        if self.straightenPreviewActive: return
        if self.hasSlices():
            reply = QMessageBox.warning(self, tr("警告：校正圖像"),
                                        tr("圖像校正將會清除所有現有切片。\n您確定要繼續嗎？"),
                                        QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
            if reply==QMessageBox.No: return
            self.clearAllSlices()
        # 重置可能殘留狀態
        self.straightenPoints = []
        self.cancelStraighten()
        self.straighteningMode       = True
        self.straightenPreviewActive = False
        self.setCursor(Qt.CrossCursor)
        self.statusBar().showMessage(tr("校正模式：拖拽繪製參考線"))

    def previewStraighten(self, p1, p2):
        # 與 cutter_mod 保持相同的角度計算邏輯
        dx, dy = p2.x()-p1.x(), p2.y()-p1.y()
        if abs(dx)<1e-6 and abs(dy)<1e-6:
            self.setCursor(Qt.ArrowCursor); self.straighteningMode=False
            self.statusBar().showMessage(tr("校正取消：未畫線")); return
        k    = dy/dx if abs(dx)>1e-6 else float('inf')
        theta = math.degrees(math.atan(abs(k)))
        # 根據斜率範圍還原您的 angle 計算
        if 0<k<1:      angle = -theta
        elif -1<k<0:   angle = theta
        elif k>1:      angle = 90-theta
        else:          angle = theta-90
        self.straightenAngle = angle
        self.statusBar().showMessage(tr(f"預覽校正：角度 {angle:.2f}°，請確認或取消"))
        # 保存原始
        self.originalPixmapBeforeStraighten = self.sliceView.image_item.pixmap()
        qim = self.originalPixmapBeforeStraighten.toImage().convertToFormat(QImage.Format_ARGB32)
        w,h = qim.width(), qim.height()
        buf = qim.bits(); buf.setsize(qim.byteCount())
        img = np.array(buf).reshape(h,w,4)
        M = getRotationMatrix2D((w/2,h/2), -angle, 1.0)
        cos, sin = abs(M[0,0]), abs(M[0,1])
        nw = int(h*sin + w*cos); nh = int(h*cos + w*sin)
        M[0,2]+= (nw/2)-(w/2); M[1,2]+= (nh/2)-(h/2)
        rot = warpAffine(img, M, (nw,nh), flags=INTER_LINEAR,
                         borderMode=BORDER_CONSTANT, borderValue=(255,255,255,255))
        qim2 = QImage(rot.data, nw,nh, rot.strides[0], QImage.Format_ARGB32)
        pix2 = QPixmap.fromImage(qim2)
        self.sliceView.image_item.setPixmap(pix2)
        self.sliceView.scene().setSceneRect(QRectF(pix2.rect()))
        self.sliceView.centerOn(self.sliceView.image_item)
        # 顯示按鈕
        self.straighteningMode=False; self.straightenPreviewActive=True
        self.setCursor(Qt.ArrowCursor)
        self.straightWidget.btnStraight.hide()
        self.straightWidget.btnConfirm.show()
        self.straightWidget.btnCancel.show()

    def confirmStraighten(self):
        if not self.straightenPreviewActive:
            return
        # 覆蓋原圖
        src = self.currentImagePath
        self.sliceView.image_item.pixmap().save(src)
        self.clearProjectEdited()
        self.markProjectEdited()
        # 錄製脚本：只記錄角度
        if self.recorder.is_recording:
            self.recorder.log_action("straighten", f"{self.straightenAngle:.2f}")
        # 顯示正確提示
        self.statusBar().showMessage(tr(f"圖像已校正 {self.straightenAngle:.2f}°"))
        # 清理預覽相關 UI
        self.straightWidget.btnConfirm.hide()
        self.straightWidget.btnCancel.hide()
        self.straightWidget.btnStraight.show()
        self.straighteningMode = False
        self.straightenPreviewActive = False
        self.originalPixmapBeforeStraighten = None
        self.setCursor(Qt.ArrowCursor)

    def cancelStraighten(self):
        if self.originalPixmapBeforeStraighten:
            pix = self.originalPixmapBeforeStraighten
            self.sliceView.image_item.setPixmap(pix)
            self.sliceView.scene().setSceneRect(QRectF(pix.rect()))
            self.sliceView.centerOn(self.sliceView.image_item)
        self.statusBar().showMessage(tr("校正已取消") if self.straightenPreviewActive else tr("準備就緒"))
        self.straighteningMode=False; self.straightenPreviewActive=False
        self.setCursor(Qt.ArrowCursor)
        self.straightWidget.btnStraight.show()
        self.straightWidget.btnConfirm.hide()
        self.straightWidget.btnCancel.hide()
        self.originalPixmapBeforeStraighten=None
        # 移除臨時線條
        if self.tempStraightenLine and self.tempStraightenLine.scene():
            self.sliceView.scene().removeItem(self.tempStraightenLine)
        self.tempStraightenLine=None

    def startCropMode(self):
        # 不可在校正模式下啓動裁剪
        if self.straighteningMode or self.straightenPreviewActive:
            QApplication.beep()
            self.statusBar().showMessage(tr("校正模式激活中，無法進入裁剪模式"))
            return
        if not self.sliceView.image_item:
            QApplication.beep(); self.statusBar().showMessage(tr("請先導入圖片")); return
        if self.hasSlices():
            reply = QMessageBox.warning(self, tr("警告：裁剪圖像"),
                                        tr("圖像裁剪將清除所有現有切片。\n確定要繼續？"),
                                        QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
            if reply==QMessageBox.No: return
            self.clearAllSlices()
        # 進入裁剪
        self.croppingMode = True
        self.sliceView.setCursor(Qt.CrossCursor)
        self.straightWidget.btnCrop.hide()
        self.straightWidget.btnConfirmCrop.show()
        self.straightWidget.btnCancelCrop.show()
        # 在整張圖上建立一個可調大小的裁剪框
        rect = self.sliceView.scene().sceneRect()
        self.cropRectItem = SliceRect(rect, 0)
        self.sliceView.scene().addItem(self.cropRectItem)

        # 只保留邊緣調整，禁用整體移動／刪除，並始終選中以顯示手柄
        from PyQt5.QtWidgets import QGraphicsItem
        self.cropRectItem.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.cropRectItem.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.cropRectItem.setSelected(True)
        self.cropRectItem.updateHandles()

    def confirmCrop(self):
        if not self.cropRectItem: return
        # 執行裁剪並覆蓋原圖
        r = self.cropRectItem.rect().toRect()
        img = self.sliceView.image_item.pixmap().toImage()
        cropped = img.copy(r)
        cropped.save(self.currentImagePath)
        # 先退出裁剪模式並移除裁剪框，避免 scene.clear() 後二次移除
        self.cancelCrop()
        # 重新載入圖像（會清空場景），並清空切片列表
        self.sliceView.loadImage(self.currentImagePath)
        self.updateSliceList()
        self.markProjectEdited()
        self.statusBar().showMessage(tr("裁剪完成"))
        if self.recorder.is_recording:
            self.recorder.log_action("crop")

    def cancelCrop(self):
        # 退出裁剪模式
        self.croppingMode = False
        self.sliceView.setCursor(Qt.ArrowCursor)
        self.straightWidget.btnCrop.show()
        self.straightWidget.btnConfirmCrop.hide()
        self.straightWidget.btnCancelCrop.hide()
        
        if self.cropRectItem:
            # 只在裁剪框還在場景中時移除，並忽略已刪除錯誤
            scene = self.cropRectItem.scene()
            if scene:
                try:
                    scene.removeItem(self.cropRectItem)
                except RuntimeError:
                    pass
            self.cropRectItem = None
        self.clearAllSlices()
        self.statusBar().showMessage(tr("裁剪已取消"))

    # helper: 判斷是否有切片
    def hasSlices(self):
        return any(isinstance(it, SliceRect) for it in self.sliceView.scene().items())

    def toggle_recording(self):
        if self.recorder.is_recording:
            self.recorder.stop()
            self.save_script()
            self.auto_process_panel.btn_record.setText(tr("錄製脚本"))
            self.statusBar().showMessage(tr("脚本錄製已結束"))
        else:
            self.recorder.start()
            self.auto_process_panel.btn_record.setText(tr("停止錄製"))
            self.statusBar().showMessage(tr("脚本錄製中..."))

    def save_script(self):
        # 取得現有脚本名稱，找出最大編號
        if not self.recorder.actions:  # 若脚本內容為空則不保存
            self.statusBar().showMessage(tr("脚本內容為空，未保存脚本文件"))
            return
        existing = [f.stem for f in self.auto_process_panel.script_dir.glob("*.cscript")]
        nums = []
        for name in existing:
            if name.startswith("脚本 "):
                try:
                    nums.append(int(name.replace("脚本 ", "")))
                except:
                    pass
        next_num = max(nums) + 1 if nums else 1
        base = tr('脚本 {0}').format(next_num)
        path = self.auto_process_panel.script_dir / f"{base}.cscript"
        with open(path, 'w', encoding='utf-8') as f:
            f.write("\n".join(self.recorder.actions))
        self.update_script_list()

    def import_script(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("導入脚本"), "", tr("脚本文件 (*.cscript)"))
        if path:
            target = self.auto_process_panel.script_dir / Path(path).name
            shutil.copy(path, target)
            self.update_script_list()

    def update_script_list(self):
        self.auto_process_panel.script_list.clear()
        for f in self.auto_process_panel.script_dir.glob("*.cscript"):
            self.auto_process_panel.script_list.addItem(f.stem)

    def run_script(self):
        item = self.auto_process_panel.script_list.currentItem()
        if not item: return
        path = self.auto_process_panel.script_dir / f"{item.text()}.cscript"
        self.is_script_running = True  # <--- 新增：標記脚本運行狀態
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                self.execute_command(line.strip())
        self.is_script_running = False  # <--- 新增：脚本運行結束
        self.statusBar().showMessage(tr('已運行脚本：{0}').format(item.text()))
        QApplication.beep()

    def delete_script(self):
        item = self.auto_process_panel.script_list.currentItem()
        if not item: return
        (self.auto_process_panel.script_dir / f"{item.text()}.cscript").unlink()
        self.auto_process_panel.script_list.takeItem(self.auto_process_panel.script_list.row(item))

    def execute_command(self, cmd):
        # 基本命令解析
        if not cmd: return
        parts = cmd.split()
        action = parts[0]
        params = parts[1:]
        if action == "moveSlices":
            target, dx, dy = params[0], int(params[1]), int(params[2])
            self._moveSlices_cmd(target, dx, dy)
        elif action == "scaleSlices":
            target, sx, sy = params[0], float(params[1]), float(params[2])
            self._scaleSlices_cmd(target, sx, sy)
        elif action == "filterSlices":
            # 新的格式支持：
            # filterSlices all [w,less,80]
            # filterSlices all [w,less,80] or [h,greater,95]
            # filterSlices selected [h,equal,95]
            # filterSlices selected [h,greater,95] and [w,less,80]
            target = params[0]
            
            # 解析條件
            condition1 = None
            logic = None
            condition2 = None
            
            # 找到第一個條件（以 [ 開始）
            for i, param in enumerate(params[1:], 1):
                if param.startswith('[') and param.endswith(']'):
                    # 解析條件格式：[dimension,operator,value]
                    condition_str = param[1:-1]  # 移除方括號
                    parts = condition_str.split(',')
                    if len(parts) == 3:
                        condition1 = [parts[0], parts[1], int(parts[2])]
                        
                        # 檢査是否有邏輯操作符和第二個條件
                        if i + 1 < len(params) and params[i + 1] in ["or", "and"]:
                            logic = params[i + 1]
                            if i + 2 < len(params) and params[i + 2].startswith('[') and params[i + 2].endswith(']'):
                                condition2_str = params[i + 2][1:-1]
                                parts2 = condition2_str.split(',')
                                if len(parts2) == 3:
                                    condition2 = [parts2[0], parts2[1], int(parts2[2])]
                        break
            
            if condition1:
                self._filterSlices_cmd(target, condition1, logic, condition2)
        elif action == "autoRecognize":
            style = params[0]
            self._autoRecognize_cmd(style)
        elif action == "mergeOverlapping":
            target = params[0]
            self._mergeOverlapping_cmd(target)
        elif action == "exportSlices":
            self.exportSlices()
        elif action == "saveProject":
            self.saveProject()
        elif action == "nextImage":
            self.nextImage()
        elif action == "prevImage":
            self.prevImage()
        elif action == "normalizeSlices":
            target, width, height = params[0], int(params[1]), int(params[2])
            self._normalizeSlices_cmd(target, width, height)
        elif action == "move":
            dx, dy = int(params[0]), int(params[1])
            self._moveSelectedSlices_cmd(dx, dy)
        elif action == "straighten":
            angle = float(params[0])
            self._straighten_cmd(angle)
        elif action == "clearSliceNames":
            self.clearAllSliceNames()
        elif action == "scaleProject":
            scale_factor = float(params[0])
            self._scaleProject_cmd(scale_factor)
        elif action == "detectTable":
            style = params[0]
            min_width = int(params[1])
            min_height = int(params[2])
            threshold = float(params[3])
            self._detectTable_cmd(style, min_width, min_height, threshold)
        # 根據需要添加更多命令...

    # --- 命令執行輔助 ---
    def _moveSlices_cmd(self, target, dx, dy):
        if target == "all":
            slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        else:
            slices = []
            for listItem in self.sliceList.selectedItems():
                s = listItem.data(Qt.UserRole)
                if s:
                    slices.append(s)
        for s in slices:
            s.setRect(s.rect().translated(dx, dy))
        self.updateSliceList()
        self.markProjectEdited()

    def _scaleSlices_cmd(self, target, scaleX, scaleY):
        if target == "all":
            slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        else:
            slices = []
            for listItem in self.sliceList.selectedItems():
                s = listItem.data(Qt.UserRole)
                if s:
                    slices.append(s)
        for s in slices:
            rect = s.rect()
            cx = rect.x() + rect.width()/2
            cy = rect.y() + rect.height()/2
            new_w = rect.width() * (scaleX/100.0)
            new_h = rect.height() * (scaleY/100.0)
            new_rect = QRectF(cx - new_w/2, cy - new_h/2, new_w, new_h)
            s.setRect(new_rect)
        self.updateSliceList()
        self.markProjectEdited()

    def _filterSlices_cmd(self, target, condition1, logic, condition2):
        if target == "all":
            slices = [s for s in self.sliceView.scene().items() if isinstance(s, SliceRect)]
        else:
            slices = [s for s in self.sliceList.selectedItems() if s.data(Qt.UserRole)]
            slices = [s.data(Qt.UserRole) for s in slices]
        
        # 篩除邏輯函數
        def checkCondition(slice_rect, condition):
            w = slice_rect.rect().width()
            h = slice_rect.rect().height()
            dim, op, val = condition
            
            if dim == "w":
                size = w
            elif dim == "h":
                size = h
            else:
                return False
            
            if op == "greater":
                return size > val
            elif op == "equal":
                return size == val
            elif op == "less":
                return size < val
            return False
        
        # 根據條件移除切片
        for s in slices:
            should_remove = False
            
            # 檢査第一個條件
            condition1_result = checkCondition(s, condition1)
            
            if logic is None:
                # 只有一個條件
                should_remove = condition1_result
            else:
                # 有兩個條件
                condition2_result = checkCondition(s, condition2)
                
                # 處理相同維度的特殊情況
                if condition1[0] == condition2[0]:  # 相同維度
                    # 構成數學集合條件
                    if logic == "or":
                        should_remove = condition1_result or condition2_result
                    elif logic == "and":
                        should_remove = condition1_result and condition2_result
                else:
                    # 不同維度
                    if logic == "or":
                        should_remove = condition1_result or condition2_result
                    elif logic == "and":
                        should_remove = condition1_result and condition2_result
            
            if should_remove:
                self.sliceView.scene().removeItem(s)
        
        self.updateSliceList()
        self.markProjectEdited()

    def _autoRecognize_cmd(self, style):
        # style: "白底黑字" or "黑底白字"
        if not self.sliceView.image_item:
            return
        qimg = self.sliceView.image_item.pixmap().toImage()
        width, height = qimg.width(), qimg.height()
        ptr = qimg.bits()
        ptr.setsize(qimg.byteCount())
        img_array = np.array(ptr).reshape(height, width, 4)
        gray = cvtColor(img_array, COLOR_BGRA2GRAY)
        if style == "白底黑字":
            _, thresh = threshold(gray, 127, 255, THRESH_BINARY_INV)
        else:
            _, thresh = threshold(gray, 127, 255, THRESH_BINARY)
        contours, _ = findContours(thresh, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)
        rects = []
        for cnt in contours:
            x, y, w, h = boundingRect(cnt)
            rects.append(QRectF(x, y, w, h))
        for rect in rects:
            new_slice = SliceRect(rect, number=0)
            self.sliceView.scene().addItem(new_slice)
        self.updateSliceList()
        self.markProjectEdited()

    def _mergeOverlapping_cmd(self, target):
        if target == "all":
            slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        else:
            slices = [item for item in self.sliceView.scene().selectedItems() if isinstance(item, SliceRect)]
        if not slices:
            return
        n = len(slices)
        rects = [s.rect() for s in slices]
        visited = [False] * n
        groups = []
        def overlaps(r1, r2):
            return r1.intersects(r2)
        for i in range(n):
            if visited[i]:
                continue
            group = [i]
            stack = [i]
            visited[i] = True
            while stack:
                cur = stack.pop()
                for j in range(n):
                    if not visited[j] and overlaps(rects[cur], rects[j]):
                        if any(overlaps(rects[k], rects[j]) for k in group):
                            visited[j] = True
                            stack.append(j)
                            group.append(j)
            if len(group) > 1:
                groups.append(group)
        for group in groups:
            union_rect = rects[group[0]]
            for idx in group[1:]:
                union_rect = union_rect.united(rects[idx])
            for idx in sorted(group, reverse=True):
                self.sliceView.scene().removeItem(slices[idx])
            new_slice = SliceRect(union_rect, number=0)
            self.sliceView.scene().addItem(new_slice)
        self.updateSliceList()
        self.markProjectEdited()
        
    def _normalizeSlices_cmd(self, target, width, height):
        if target == "all":
            slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        else:
            slices = self.sliceView.scene().selectedItems()
        for s in slices:
            if isinstance(s, SliceRect):
                center = s.rect().center()
                current_rect = s.rect()
                # 處理 null 值（未勾選的維度保持原值）
                final_width = current_rect.width() if width == "null" or width is None else width
                final_height = current_rect.height() if height == "null" or height is None else height
                new_rect = QRectF(center.x() - final_width/2, center.y() - final_height/2, final_width, final_height)
                s.setRect(new_rect)
                s.updateHandles()
        self.updateSliceList()
        self.markProjectEdited()
    
    def _moveSelectedSlices_cmd(self, dx, dy):
        slices = [item for item in self.sliceView.scene().selectedItems() if isinstance(item, SliceRect)]
        for s in slices:
            s.setRect(s.rect().translated(dx, dy))
        self.updateSliceList()
        self.markProjectEdited()
        
    def _straighten_cmd(self, angle):
        if not self.currentImagePath or not self.sliceView.image_item:
            return
        img = QImage(self.currentImagePath)
        tr = QTransform().rotate(angle)
        rot = img.transformed(tr, Qt.SmoothTransformation)
        rot.save(self.currentImagePath)
        self.sliceView.loadImage(self.currentImagePath)

    def _scaleProject_cmd(self, scale_factor):
        # 獲取所有切片
        slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        if not slices:
            return
        
        # 縮放所有切片的座標
        for s in slices:
            rect = s.rect()
            # 將座標乘以係數，並四捨五入到整數
            new_x = round(rect.x() * scale_factor)
            new_y = round(rect.y() * scale_factor)
            new_w = round(rect.width() * scale_factor)
            new_h = round(rect.height() * scale_factor)
            new_rect = QRectF(new_x, new_y, new_w, new_h)
            s.setRect(new_rect)
        
        self.updateSliceList()
        self.markProjectEdited()

    def _detectTable_cmd(self, style, min_width, min_height, threshold):
        if not self.sliceView.image_item:
            return
    
        # 獲取圖像數據
        qimg = self.sliceView.image_item.pixmap().toImage()
        width, height = qimg.width(), qimg.height()
        ptr = qimg.bits()
        ptr.setsize(qimg.byteCount())
        img_array = np.array(ptr).reshape(height, width, 4)
        
        # 轉換為灰度圖
        gray = cvtColor(img_array, COLOR_BGRA2GRAY)
        
        # 根據風格選擇進行二值化
        if style == "白底黑字":
            _, binary = threshold(gray, 127, 255, THRESH_BINARY_INV)
        else:
            _, binary = threshold(gray, 127, 255, THRESH_BINARY)
        
        # 計算投影
        h_proj = np.sum(binary, axis=1)
        v_proj = np.sum(binary, axis=0)
        
        # 尋找峰值
        def find_peaks(proj, threshold):
            peaks = []
            max_val = np.max(proj)
            for i in range(1, len(proj) - 1):
                if (proj[i-1] < proj[i] and proj[i+1] < proj[i] and 
                    proj[i] > threshold * max_val):
                    peaks.append(i)
            return peaks
        
        # 獲取橫線和豎線位置
        h_lines = find_peaks(h_proj, threshold)
        v_lines = find_peaks(v_proj, threshold)
        
        # 清空現有切片
        for item in self.sliceView.scene().items():
            if isinstance(item, SliceRect):
                self.sliceView.scene().removeItem(item)
        
        # 根據檢測結果創建切片
        slice_count = 0
        for i in range(len(h_lines) - 1):
            for j in range(len(v_lines) - 1):
                y1, y2 = h_lines[i], h_lines[i + 1]
                x1, x2 = v_lines[j], v_lines[j + 1]
                
                # 檢査尺寸是否滿足最小要求
                w = x2 - x1
                h = y2 - y1
                if w >= min_width and h >= min_height:
                    rect = QRectF(x1, y1, w, h)
                    new_slice = SliceRect(rect, slice_count + 1)
                    self.sliceView.scene().addItem(new_slice)
                    slice_count += 1
        
        self.updateSliceList()
        self.markProjectEdited()
