import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
                             QGraphicsRectItem, QFileDialog, QAction, QMessageBox, QMenu,
                             QListWidget, QWidget, QLabel, QLineEdit, QPushButton, QHBoxLayout,
                             QVBoxLayout, QDockWidget, QInputDialog, QToolButton, QAbstractItemView,
                             QDialog, QFormLayout, QSpinBox, QDoubleSpinBox, QRadioButton, QDialogButtonBox, QButtonGroup)
from PyQt5.QtGui import QPixmap, QPainter, QPen, QKeyEvent, QImage, QIcon, QIntValidator
from PyQt5.QtCore import Qt, QRectF, QPointF
import os
import json

def resource_path(relative_path):
    # 取得資源文件的絕對路徑，可在 PyInstaller 打包後正確載入
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

# 自訂切片項
class SliceRect(QGraphicsRectItem):
    def __init__(self, rect, number, *args, **kwargs):
        super().__init__(rect, *args, **kwargs)
        self.number = number
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
    
    def mousePressEvent(self, event):
        self.setSelected(True)
        # 記錄初始位置與滑鼠壓下的場景位置
        self._mousePressScenePos = event.scenePos()
        self._initialPos = self.pos()
        if self.scene() and self.scene().views():
            parent = self.scene().views()[0].parent()
            if hasattr(parent, "statusBar"):
                parent.statusBar().showMessage(f"切片 {self.number} 移動中")
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # 計算滑鼠拖移距離，低於5px則視爲選擇動作
        delta = event.scenePos() - self._mousePressScenePos
        if delta.manhattanLength() < 5:
            # 滑鼠拖移不足，恢復原位置
            self.setPos(self._initialPos)
            if self.scene() and self.scene().views():
                parent = self.scene().views()[0].parent()
                if hasattr(parent, "statusBar"):
                    rect = self.rect()
                    x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
                    parent.statusBar().showMessage(f"已選擇：切片 {self.number}（X:{x} Y:{y} 寬:{w} 高:{h}）")
        else:
            if self.scene() and self.scene().views():
                parent = self.scene().views()[0].parent()
                if hasattr(parent, "statusBar"):
                    parent.statusBar().showMessage(f"切片 {self.number} 移動完成")
        
    def paint(self, painter, option, widget):
        if self.isSelected():
            from PyQt5.QtGui import QColor
            painter.fillRect(self.rect(), QColor(0, 0, 255, 100))
            pen = QPen(Qt.green, 3)
        else:
            pen = QPen(Qt.red, 2)
        painter.setPen(pen)
        painter.drawRect(self.rect())

    def contextMenuEvent(self, event):
        menu = QMenu()
        act = menu.addAction("刪除切片")
        if menu.exec_(event.screenPos()) == act:
            if self.scene() and self.scene().views():
                parent = self.scene().views()[0].parent()
                if hasattr(parent, "statusBar"):
                    parent.statusBar().showMessage("已刪除選定切片")
                if hasattr(parent, "markProjectEdited"):
                    parent.markProjectEdited()
            scene = self.scene()
            scene.removeItem(self)
            scene.update()
            if scene and scene.views():
                view = scene.views()[0]
                if hasattr(view.parent(), "updateSliceList"):
                    view.parent().updateSliceList()

# 自訂「固定寬高」窗口
class SliceDimensionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lblWidth = QLabel("寬度:")
        self.editWidth = QLineEdit()
        self.editWidth.setValidator(QIntValidator(1, 10000, self))  # 限制必須為正整數
        lblHeight = QLabel("高度:")
        self.editHeight = QLineEdit()
        self.editHeight.setValidator(QIntValidator(1, 10000, self))  # 限制必須為正整數
        self.btnConfirm = QPushButton("確定")
        self.btnConfirm.clicked.connect(self.onConfirm)
        self.btnReset = QPushButton("重置")
        self.btnReset.clicked.connect(self.onReset)
        
        hLayout1 = QHBoxLayout()
        hLayout1.addWidget(lblWidth)
        hLayout1.addWidget(self.editWidth)
        hLayout2 = QHBoxLayout()
        hLayout2.addWidget(lblHeight)
        hLayout2.addWidget(self.editHeight)
        hbtnLayout = QHBoxLayout()
        hbtnLayout.addWidget(self.btnConfirm)
        hbtnLayout.addWidget(self.btnReset)
        vLayout = QVBoxLayout()
        vLayout.addLayout(hLayout1)
        vLayout.addLayout(hLayout2)
        vLayout.addLayout(hbtnLayout)
        self.setLayout(vLayout)
        self.setFixedHeight(150)
        
    def onConfirm(self):
        try:
            width = int(self.editWidth.text())
            height = int(self.editHeight.text())
            if width > 0 and height > 0:
                self.window().fixedSliceSize = (width, height)
                self.window().statusBar().showMessage(f"固定切片尺寸：{width} x {height}")
            else:
                self.window().fixedSliceSize = None
                self.window().statusBar().showMessage("切片尺寸無效，恢復自由模式")
        except ValueError:
            self.window().fixedSliceSize = None
            self.window().statusBar().showMessage("未指定切片尺寸，使用自由模式")
    
    def onReset(self):
        self.editWidth.clear()
        self.editHeight.clear()
        self.window().fixedSliceSize = None
        self.window().statusBar().showMessage("固定寬高已重置")

# 劃分切片對話框
class DivideSlicesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("劃分切片")
        layout = QFormLayout(self)
        self.spinCols = QSpinBox(self)
        self.spinRows = QSpinBox(self)
        layout.addRow("每橫行切片數量：", self.spinCols)
        layout.addRow("每縱列切片數量：", self.spinRows)
        self.radioCorner = QRadioButton("對角點", self)
        self.radioCenter = QRadioButton("對角切片中心點", self)
        self.radioCorner.setChecked(True)
        radioLayout = QHBoxLayout()
        radioLayout.addWidget(self.radioCorner)
        radioLayout.addWidget(self.radioCenter)
        layout.addRow("定位方式：", radioLayout)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)
    def getValues(self):
        method = "corner" if self.radioCorner.isChecked() else "center"
        return self.spinCols.value(), self.spinRows.value(), method

# 自訂繪圖視圖
class SliceView(QGraphicsView):
    def __init__(self, parent):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.image_item = None
        self.drawing = False
        self.fixedMode = False
        self.start_pos = QPointF()
        self.tempRect = None
        # 新增選區屬性
        self.selecting = False
        self.startSelectPos = QPointF()
        self.rubberRect = None
        self.panning = False
        self.setMouseTracking(True)
        # 記錄是否開始拖拽
        self.selectionDragStarted = False

    def loadImage(self, image_path):
        pixmap = QPixmap(image_path)
        self.scene().clear()
        self.scene().setSceneRect(QRectF(pixmap.rect()))
        self.image_item = self.scene().addPixmap(pixmap)

    def mousePressEvent(self, event):
        # 優先處理劃分切片模式
        if event.button() == Qt.LeftButton and hasattr(self.parent(), "dividingSlices") and self.parent().dividingSlices:
            pt = self.mapToScene(event.pos())
            mainw = self.parent()
            mainw.dividePoints.append(pt)
            if len(mainw.dividePoints) == 1:
                mainw.statusBar().showMessage("劃分切片：請點選第二個點")
            elif len(mainw.dividePoints) == 2:
                mainw.divideSlices()
                mainw.dividingSlices = False
                mainw.dividePoints = []
            return
        if event.button() == Qt.LeftButton and (event.modifiers() & Qt.ControlModifier):
            self.startSelectPos = self.mapToScene(event.pos())
            self.selecting = True
            self.selectionDragStarted = False
        if event.button() == Qt.LeftButton and (event.modifiers() & Qt.ControlModifier):
            item = self.scene().itemAt(self.mapToScene(event.pos()), self.transform())
            if item and isinstance(item, SliceRect):
                item.setSelected(True)
            return
        if event.button() == Qt.LeftButton:
            fixedSize = getattr(self.parent(), "fixedSliceSize", None)
            if (fixedSize):
                self.fixedMode = True
                # 取得鼠標點作爲中心點
                self.mouse_center = self.mapToScene(event.pos())
                from PyQt5.QtCore import QSizeF
                self.fixedWidth, self.fixedHeight = fixedSize
                # 根據中心點計算虛線框位置
                rect = QRectF(
                    self.mouse_center.x() - self.fixedWidth/2,
                    self.mouse_center.y() - self.fixedHeight/2,
                    self.fixedWidth,
                    self.fixedHeight
                )
                self.tempRect = self.scene().addRect(rect, QPen(Qt.green, 2, Qt.DashLine))
                return
        if event.button() == Qt.LeftButton and QApplication.keyboardModifiers() != Qt.KeyboardModifier(Qt.Key_Space):
            item = self.scene().itemAt(self.mapToScene(event.pos()), self.transform())
            if not (item and isinstance(item, SliceRect)):
                self.scene().clearSelection()
        if event.button() == Qt.LeftButton and QApplication.keyboardModifiers() == Qt.KeyboardModifier(Qt.Key_Space):
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            super().mousePressEvent(event)
            return
        if event.button() == Qt.LeftButton:
            self.start_pos = self.mapToScene(event.pos())
            self.drawing = True
            self.tempRect = self.scene().addRect(QRectF(self.start_pos, self.start_pos),
                                                 QPen(Qt.green, 2, Qt.DashLine))
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.selecting:
            current_select_pos = self.mapToScene(event.pos())
            if (current_select_pos - self.startSelectPos).manhattanLength() > 5:
                self.selectionDragStarted = True
                rect = QRectF(self.startSelectPos, current_select_pos).normalized()
                if not self.rubberRect:
                    self.rubberRect = self.scene().addRect(rect, QPen(Qt.blue, 1, Qt.DashLine))
                else:
                    self.rubberRect.setRect(rect)
            return
        if self.fixedMode and self.tempRect is not None:
            # 更新虛線框，使鼠標始終處於中心位置
            new_center = self.mapToScene(event.pos())
            rect = QRectF(
                new_center.x() - self.fixedWidth/2,
                new_center.y() - self.fixedHeight/2,
                self.fixedWidth,
                self.fixedHeight
            )
            self.tempRect.setRect(rect)
        elif self.drawing and self.tempRect is not None:
            current_pos = self.mapToScene(event.pos())
            rect = QRectF(self.start_pos, current_pos).normalized()
            self.tempRect.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.selecting:
            if self.selectionDragStarted and self.rubberRect:
                rect = self.rubberRect.rect()
                for s in self.scene().items():
                    if isinstance(s, SliceRect) and rect.contains(s.sceneBoundingRect()):
                        s.setSelected(True)
                self.scene().removeItem(self.rubberRect)
                self.rubberRect = None
            self.selecting = False
            self.selectionDragStarted = False
            return
        if self.fixedMode and self.tempRect is not None:
            rect = self.tempRect.rect()
            self.scene().removeItem(self.tempRect)
            self.tempRect = None
            self.fixedMode = False
            slice_number = len([item for item in self.scene().items() if isinstance(item, SliceRect)]) + 1
            new_slice = SliceRect(rect, slice_number)
            self.scene().addItem(new_slice)
            self.scene().clearSelection()
            new_slice.setSelected(True)
            if hasattr(self.parent(), "updateSliceList"):
                self.parent().updateSliceList()
            if hasattr(self.parent(), "statusBar"):
                x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
                self.parent().statusBar().showMessage(f"創建成功：切片 {new_slice.number}（{x},{y} | {w}x{h}）")
            if hasattr(self.parent(), "markProjectEdited"):
                self.parent().markProjectEdited()
        elif self.drawing and self.tempRect is not None:
            rect = self.tempRect.rect()
            self.scene().removeItem(self.tempRect)
            self.tempRect = None
            self.drawing = False
            if rect.width() < 5 or rect.height() < 5:
                return
            slice_number = len([item for item in self.scene().items() if isinstance(item, SliceRect)]) + 1
            new_slice = SliceRect(rect, slice_number)
            self.scene().addItem(new_slice)
            self.scene().clearSelection()
            new_slice.setSelected(True)
            if hasattr(self.parent(), "updateSliceList"):
                self.parent().updateSliceList()
            if hasattr(self.parent(), "statusBar"):
                x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
                self.parent().statusBar().showMessage(f"創建成功：切片 {new_slice.number}（{x},{y} | {w}x{h}）")
            if hasattr(self.parent(), "markProjectEdited"):
                self.parent().markProjectEdited()
        else:
            super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.NoDrag)

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                self.zoomIn()
                pass
            elif event.key() == Qt.Key_Minus:
                self.zoomOut()
                pass
        if event.key() == Qt.Key_Delete:
            for item in self.scene().selectedItems():
                if isinstance(item, SliceRect):
                    self.scene().removeItem(item)
                pass
            self.scene().update()
            if hasattr(self.parent(), "updateSliceList"):
                self.parent().updateSliceList()
                pass
            if hasattr(self.parent(), "statusBar"):
                self.parent().statusBar().showMessage("已刪除選定切片")
                pass
            if hasattr(self.parent(), "markProjectEdited"):
                self.parent().markProjectEdited()
                pass
            return
        # 處理方向鍵移動
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = 10 if event.modifiers() & Qt.ShiftModifier else 1
            dx, dy = 0, 0
            if event.key() == Qt.Key_Left:
                dx = -step
            elif event.key() == Qt.Key_Right:
                dx = step
            elif event.key() == Qt.Key_Up:
                dy = -step
            elif event.key() == Qt.Key_Down:
                dy = step
            for item in self.scene().selectedItems():
                if isinstance(item, SliceRect):
                    item.moveBy(dx, dy)
            self.scene().update()
            event.accept()  # 避免事件傳遞導致選取被取消
            return
        if self.scene().selectedItems():
            item = self.scene().selectedItems()[0]
            if isinstance(item, SliceRect):
                delta = 1
                rect = item.rect()
                if event.key() == Qt.Key_Left:
                    item.setRect(rect.translated(-delta, 0))
                elif event.key() == Qt.Key_Right:
                    item.setRect(rect.translated(delta, 0))
                elif event.key() == Qt.Key_Up:
                    item.setRect(rect.translated(0, -delta))
                elif event.key() == Qt.Key_Down:
                    item.setRect(rect.translated(0, delta))
                if hasattr(self.parent(), "markProjectEdited"):
                    self.parent().markProjectEdited()
                pass
        super().keyPressEvent(event)

    def zoomIn(self):
        self.scale(1.25, 1.25)

    def zoomOut(self):
        self.scale(0.8, 0.8)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoomIn()
            else:
                self.zoomOut()
        else:
            super().wheelEvent(event)

# 修改 SliceListWidget 類：啓用內部拖放並重載 dropEvent
class SliceListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)  # 支援 Ctrl/Shift/拖曳多選
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        self.setDragDropMode(QAbstractItemView.InternalMove)  # 啓用拖放排序

    def dropEvent(self, event):
        super().dropEvent(event)
        if hasattr(self.window(), "reorderSlices"):
            self.window().reorderSlices()
        if hasattr(self.window(), "markProjectEdited"):
            self.window().markProjectEdited()

    def showContextMenu(self, pos):
        menu = QMenu(self)
        deleteAction = menu.addAction("刪除切片")
        action = menu.exec_(self.mapToGlobal(pos))
        if action == deleteAction:
            self.deleteSelectedItems()
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.deleteSelectedItems()
        else:
            super().keyPressEvent(event)
    def deleteSelectedItems(self):
        main_win = self.window()
        for item in self.selectedItems():
            slice_item = item.data(Qt.UserRole)
            if slice_item:
                scene = slice_item.scene()
                if scene:
                    scene.removeItem(slice_item)
        if hasattr(main_win, "updateSliceList"):
            main_win.updateSliceList()
        if main_win.sliceView.scene():
            main_win.sliceView.scene().update()
        if hasattr(main_win, "statusBar"):
            main_win.statusBar().showMessage("已刪除選定切片")
        if hasattr(main_win, "markProjectEdited"):
            main_win.markProjectEdited()

# 修改 移動切片對話框：將「全部」與「已選擇」橫向佈局
class MoveSlicesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("移動切片")
        layout = QFormLayout(self)
        # 改成橫向排列
        self.radioAll = QRadioButton("全部", self)
        self.radioSelected = QRadioButton("已選擇", self)
        self.radioAll.setChecked(True)
        radioLayout = QHBoxLayout()
        radioLayout.addWidget(self.radioAll)
        radioLayout.addWidget(self.radioSelected)
        layout.addRow("切片範圍：", radioLayout)
        self.spinX = QSpinBox(self)
        self.spinX.setRange(-10000, 10000)
        self.spinX.setValue(0)
        self.spinX.setSuffix(" px")
        self.spinY = QSpinBox(self)
        self.spinY.setRange(-10000, 10000)
        self.spinY.setValue(0)
        self.spinY.setSuffix(" px")
        layout.addRow("向右移動：", self.spinX)
        layout.addRow("向下移動：", self.spinY)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)

    def getValues(self):
        target = "all" if self.radioAll.isChecked() else "selected"
        return target, self.spinX.value(), self.spinY.value()

# 修改 縮放切片對話框：將「全部」與「已選擇」橫向佈局
class ScaleSlicesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("縮放切片")
        layout = QFormLayout(self)
        # 改成橫向排列
        self.radioAll = QRadioButton("全部", self)
        self.radioSelected = QRadioButton("已選擇", self)
        self.radioAll.setChecked(True)
        radioLayout = QHBoxLayout()
        radioLayout.addWidget(self.radioAll)
        radioLayout.addWidget(self.radioSelected)
        layout.addRow("切片範圍：", radioLayout)
        self.spinX = QDoubleSpinBox(self)
        self.spinX.setRange(0.01, 1000.00)
        self.spinX.setDecimals(2)
        self.spinX.setValue(100.00)
        self.spinX.setSuffix(" %")
        self.spinY = QDoubleSpinBox(self)
        self.spinY.setRange(0.01, 1000.00)
        self.spinY.setDecimals(2)
        self.spinY.setValue(100.00)
        self.spinY.setSuffix(" %")
        layout.addRow("橫向比例：", self.spinX)
        layout.addRow("縱向比例：", self.spinY)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)

    def getValues(self):
        target = "all" if self.radioAll.isChecked() else "selected"
        return target, self.spinX.value(), self.spinY.value()

class FilterSlicesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("篩選切片")
        layout = QFormLayout(self)
        # 切片範圍單選群組
        self.radioAll = QRadioButton("全部", self)
        self.radioSelected = QRadioButton("已選擇", self)
        self.radioAll.setChecked(True)
        self.rangeGroup = QButtonGroup(self)
        self.rangeGroup.addButton(self.radioAll)
        self.rangeGroup.addButton(self.radioSelected)
        radioLayout = QHBoxLayout()
        radioLayout.addWidget(self.radioAll)
        radioLayout.addWidget(self.radioSelected)
        layout.addRow("切片範圍：", radioLayout)
        # 篩選條件單選群組
        self.radioLess = QRadioButton("小於", self)
        self.radioGreater = QRadioButton("大於", self)
        self.radioLess.setChecked(True)
        self.conditionGroup = QButtonGroup(self)
        self.conditionGroup.addButton(self.radioLess)
        self.conditionGroup.addButton(self.radioGreater)
        conditionLayout = QHBoxLayout()
        conditionLayout.addWidget(self.radioLess)
        conditionLayout.addWidget(self.radioGreater)
        layout.addRow("篩選條件：", conditionLayout)
        self.spinThreshold = QSpinBox(self)
        self.spinThreshold.setRange(1, 10000)
        self.spinThreshold.setValue(10)
        self.spinThreshold.setSuffix(" px")
        layout.addRow("切片寬高閾值：", self.spinThreshold)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)

    def getValues(self):
        target = "all" if self.radioAll.isChecked() else "selected"
        condition = "lt" if self.radioLess.isChecked() else "gt"
        return target, condition, self.spinThreshold.value()

# 主視窗
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("囫圇切 HulenCut v0.5")
        self.setWindowIcon(QIcon(resource_path("hulencutter.ico")))
        self.resize(800, 600)
        self.fixedSliceSize = None
        self.sliceView = SliceView(self)
        self.setCentralWidget(self.sliceView)
        self.createToolBar()
        self.statusBar().showMessage("準備就緒")
        # 預設導出目錄與格式
        self.defaultExportDir = ""
        self.defaultExportFormat = "PNG"
        # 支援導入文件夾以及圖片導航
        self.currentFolder = ""
        self.folderImages = []
        self.currentImageIndex = -1
        self.sliceList = SliceListWidget(self)
        # 在頂部添加操作按鈕
        sliceListContainer = QWidget(self)
        vLayout = QVBoxLayout(sliceListContainer)
        # 新增水平佈局，放置「置頂」「上移」「下移」「置底」按鈕
        btnLayout = QHBoxLayout()
        self.btnTop = QPushButton("置頂", self)
        self.btnTop.clicked.connect(self.topSlice)
        self.btnUp = QPushButton("上移", self)
        self.btnUp.clicked.connect(self.upSlice)
        self.btnDown = QPushButton("下移", self)
        self.btnDown.clicked.connect(self.downSlice)
        self.btnBottom = QPushButton("置底", self)
        self.btnBottom.clicked.connect(self.bottomSlice)
        btnLayout.addWidget(self.btnTop)
        btnLayout.addWidget(self.btnUp)
        btnLayout.addWidget(self.btnDown)
        btnLayout.addWidget(self.btnBottom)
        vLayout.addLayout(btnLayout)
        vLayout.addWidget(self.sliceList)
        sliceListContainer.setLayout(vLayout)
        # 原有清空切片按鈕與列表
        btnClear = QPushButton("清空切片", self)
        btnClear.clicked.connect(self.clearAllSlices)
        vLayout.addWidget(btnClear)
        dockList = QDockWidget("切片列表", self)
        dockList.setWidget(sliceListContainer)
        self.addDockWidget(Qt.LeftDockWidgetArea, dockList)
        self.sliceList.itemClicked.connect(self.onSliceItemClicked)
        # 連結列表多選事件
        self.sliceList.itemSelectionChanged.connect(self.onSliceSelectionChanged)
        self.sliceDimWidget = SliceDimensionWidget(self)
        dockDim = QDockWidget("固定寬高", self)
        dockDim.setWidget(self.sliceDimWidget)
        self.addDockWidget(Qt.LeftDockWidgetArea, dockDim)
        self.splitDockWidget(dockList, dockDim, Qt.Vertical)
        self.currentImagePath = None  # 儲存當前圖片完整路徑
        # 連結 scene 的 selectionChanged 信號
        self.sliceView.scene().selectionChanged.connect(self.syncListSelectionWithScene)
        self.projectEdited = False  # 新增工程狀態標誌
        self.dividingSlices = False      # 劃分切片模式旗標
        self.dividePoints = []           # 儲存使用者點選的兩個點
        self.divide_params = None        # 儲存劃分參數 (cols, rows, method)

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
        currentRow = self.sliceList.currentRow()
        if currentRow < 0: return
        item = self.sliceList.takeItem(currentRow)
        self.sliceList.insertItem(0, item)
        self.sliceList.setCurrentRow(0)
        self.reorderSlices()
        self.markProjectEdited()

    # 上移
    def upSlice(self):
        currentRow = self.sliceList.currentRow()
        if currentRow <= 0: return
        item = self.sliceList.takeItem(currentRow)
        self.sliceList.insertItem(currentRow - 1, item)
        self.sliceList.setCurrentRow(currentRow - 1)
        self.reorderSlices()
        self.markProjectEdited()

    # 下移
    def downSlice(self):
        currentRow = self.sliceList.currentRow()
        if currentRow < 0 or currentRow >= self.sliceList.count() - 1: return
        item = self.sliceList.takeItem(currentRow)
        self.sliceList.insertItem(currentRow + 1, item)
        self.sliceList.setCurrentRow(currentRow + 1)
        self.reorderSlices()
        self.markProjectEdited()

    # 置底
    def bottomSlice(self):
        currentRow = self.sliceList.currentRow()
        if currentRow < 0: return
        item = self.sliceList.takeItem(currentRow)
        self.sliceList.insertItem(self.sliceList.count(), item)
        self.sliceList.setCurrentRow(self.sliceList.count() - 1)
        self.reorderSlices()
        self.markProjectEdited()

    def updateSliceList(self):
        # 重新編號所有切片(避免存在重複編號)
        slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        slices.sort(key=lambda s: s.number)
        for i, s in enumerate(slices):
            s.number = i + 1

        # 保存當前選中的切片
        current_item = self.sliceList.currentItem()
        selected_slice = current_item.data(Qt.UserRole) if current_item else None
        self.sliceList.clear()
        for s in slices:
            rect = s.rect()
            x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
            from PyQt5.QtWidgets import QListWidgetItem
            item = QListWidgetItem(f"切片 {s.number}（{x},{y} | {w}x{h}）")
            item.setData(Qt.UserRole, s)
            self.sliceList.addItem(item)
        # 恢復先前選中的切片
        if selected_slice is not None:
            for i in range(self.sliceList.count()):
                if self.sliceList.item(i).data(Qt.UserRole) is selected_slice:
                    self.sliceList.setCurrentRow(i)
                    break

    def onSliceItemClicked(self, item):
        if item.isSelected() and len(self.sliceList.selectedItems()) == 1:
            s = item.data(Qt.UserRole)
            if s:
                rect = s.rect()
                self.statusBar().showMessage(
                    f"已選擇：切片 {s.number}（X:{int(rect.x())} Y:{int(rect.y())} 寬:{int(rect.width())} 高:{int(rect.height())}）"
                )
                # 當單選時，視圖自動移動到該切片所在位置
                self.sliceView.centerOn(s)
        else:
            self.statusBar().showMessage(f"已選擇 {len(self.sliceList.selectedItems())} 份切片")

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
            self.statusBar().showMessage("已取消選擇")
        elif selected_count > 1:
            self.statusBar().showMessage(f"已選擇 {selected_count} 份切片")
        else:
            self.statusBar().showMessage("已選擇 1 份切片")

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
            self.statusBar().showMessage("已取消選擇")
        elif count > 1:
            self.statusBar().showMessage(f"已選擇 {count} 份切片")
        else:
            selected_slice = next(iter(selected_slices))
            rect = selected_slice.rect()
            self.statusBar().showMessage(
                f"已選擇：切片 {selected_slice.number}（X:{int(rect.x())} Y:{int(rect.y())} 寬:{int(rect.width())} 高:{int(rect.height())}）"
            )

    def createToolBar(self):
        toolbar = self.addToolBar("工具")
        fileMenu = QMenu("導入", self)
        actOpenImg = QAction("導入圖片", self)
        actOpenImg.triggered.connect(self.openImage)
        actOpenImg.setShortcut("Ctrl+O")
        fileMenu.addAction(actOpenImg)
        actOpenFolder = QAction("導入文件夾", self)
        actOpenFolder.triggered.connect(self.openFolder)
        actOpenFolder.setShortcut("Ctrl+Shift+O")
        fileMenu.addAction(actOpenFolder)
        actOpenProject = QAction("導入工程", self)
        actOpenProject.triggered.connect(self.openProject)
        actOpenProject.setShortcut("Ctrl+P")
        fileMenu.addAction(actOpenProject)
        # 「導入看典古籍json」選項
        actOpenKandian = QAction("導入看典古籍json", self)
        actOpenKandian.triggered.connect(self.importKandianJson)
        fileMenu.addAction(actOpenKandian)
        fileButton = QToolButton(self)
        fileButton.setText("導入")
        fileButton.setMenu(fileMenu)
        fileButton.setPopupMode(QToolButton.InstantPopup)
        toolbar.addWidget(fileButton)
        
        exportMenu = QMenu("導出", self)
        actExportSlices = QAction("導出切片", self)
        actExportSlices.triggered.connect(self.exportSlices)
        actExportSlices.setShortcut("Ctrl+E")
        exportMenu.addAction(actExportSlices)
        actUpdateDefault = QAction("設定導出預設", self)
        actUpdateDefault.triggered.connect(self.updateExportDefaults)
        exportMenu.addAction(actUpdateDefault)
        actSaveProject = QAction("保存工程", self)
        actSaveProject.triggered.connect(self.saveProject)
        actSaveProject.setShortcut("Ctrl+S")
        exportMenu.addAction(actSaveProject)
        actSaveProjectAs = QAction("工程另存爲", self)
        actSaveProjectAs.triggered.connect(self.saveProjectAs)
        actSaveProjectAs.setShortcut("Ctrl+Shift+S")
        exportMenu.addAction(actSaveProjectAs)
        exportButton = QToolButton(self)
        exportButton.setText("導出")
        exportButton.setMenu(exportMenu)
        exportButton.setPopupMode(QToolButton.InstantPopup)
        toolbar.addWidget(exportButton)
        
        # 動作下拉選單
        actionMenu = QMenu("動作", self)
        actMove = QAction("移動切片", self)
        actMove.triggered.connect(self.openMoveSlicesDialog)
        actionMenu.addAction(actMove)
        actScale = QAction("縮放切片", self)
        actScale.triggered.connect(self.openScaleSlicesDialog)
        actionMenu.addAction(actScale)
        actFilter = QAction("篩選切片", self)
        actFilter.triggered.connect(self.filterSlices)
        actionMenu.addAction(actFilter)
        actDivide = QAction("劃分切片", self)
        actDivide.triggered.connect(self.openDivideSlicesDialog)
        actionMenu.addAction(actDivide)
        actionButton = QToolButton(self)
        actionButton.setText("動作")
        actionButton.setMenu(actionMenu)
        actionButton.setPopupMode(QToolButton.InstantPopup)
        toolbar.addWidget(actionButton)

        # 獨立按鈕：上一張、下一張、關於
        prevAct = QAction("上一張", self)
        prevAct.triggered.connect(self.prevImage)
        prevAct.setShortcut("Ctrl+Left")
        prevAct.setToolTip("Ctrl+Left")
        toolbar.addAction(prevAct)
        nextAct = QAction("下一張", self)
        nextAct.triggered.connect(self.nextImage)
        nextAct.setShortcut("Ctrl+Right")
        nextAct.setToolTip("Ctrl+Right")
        toolbar.addAction(nextAct)
        aboutAct = QAction("關於", self)
        aboutAct.triggered.connect(self.showAbout)
        toolbar.addAction(aboutAct)

    def updateExportDefaults(self):
        # 讓用戶指定預設導出目錄
        dir_path = QFileDialog.getExistingDirectory(self, "選擇預設導出目錄", self.defaultExportDir)
        if dir_path:
            self.defaultExportDir = dir_path
        # 讓用戶指定預設格式
        formats = ["PNG", "JPG", "BMP"]
        try:
            current_index = formats.index(self.defaultExportFormat)
        except ValueError:
            current_index = 0
        fmt, ok = QInputDialog.getItem(self, "設定預設格式", "導出格式：", formats, current_index, False)
        if ok:
            self.defaultExportFormat = fmt
            self.statusBar().showMessage(f"更新導出預設：格式爲 {fmt}；目錄爲 {self.defaultExportDir}")

    # 導入文件夾
    def openFolder(self):
        folder = QFileDialog.getExistingDirectory(self, "選擇文件夾", "")
        if folder:
            self.currentFolder = folder
            self.folderImages = sorted([
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith((".png", ".jpg", ".bmp"))
            ])
            if self.folderImages:
                self.currentImageIndex = 0
                self.loadCurrentFolderImage()

    def loadCurrentFolderImage(self):
        path = self.folderImages[self.currentImageIndex]
        self.sliceView.loadImage(path)
        self.sliceList.clear()
        filename = os.path.basename(path)
        self.statusBar().showMessage(f"載入圖片：{filename}")
        self.originalBaseName = os.path.splitext(filename)[0]
        self.currentImagePath = path  # 儲存圖片路徑
        self.checkAndLoadProject()     # 自動檢查工程文件

    # 圖片導航前確認是否捨棄現有切片
    def getCurrentProjectData(self):
        slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        slices.sort(key=lambda s: s.number)
        return "\n".join(["\t".join([
            str(int(item.rect().x())),
            str(int(item.rect().y())),
            str(int(item.rect().width())),
            str(int(item.rect().height()))
        ]) for item in slices])

    def confirmDiscardSlices(self):
        if not self.currentImagePath:
            return True
        if not self.projectEdited:
            return True
        msgBox = QMessageBox(self)
        msgBox.setWindowTitle("保存工程")
        msgBox.setText("要保存當前工程嗎？")
        btnSave = msgBox.addButton("保存", QMessageBox.AcceptRole)
        btnDont = msgBox.addButton("不保存", QMessageBox.DestructiveRole)
        btnCancel = msgBox.addButton("取消", QMessageBox.RejectRole)
        msgBox.exec_()
        if msgBox.clickedButton() == btnSave:
            self.saveProject()
            return True
        elif msgBox.clickedButton() == btnDont:
            return True
        else:
            return False

    def closeEvent(self, event):
        if self.confirmDiscardSlices():
            event.accept()
        else:
            event.ignore()

    def nextImage(self):
        if not self.folderImages:
            QApplication.beep()   # 無文件夾時發聲
            self.statusBar().showMessage("請先導入文件夾")
            return
        if not self.confirmDiscardSlices():
            return
        if self.currentImageIndex < len(self.folderImages) - 1:
            self.currentImageIndex += 1
            self.loadCurrentFolderImage()
        else:
            QApplication.beep()   # 已達最後一張時發聲
            self.statusBar().showMessage("已是最後一張")

    def prevImage(self):
        if not self.folderImages:
            QApplication.beep()   # 無文件夾時發聲
            self.statusBar().showMessage("請先導入文件夾")
            return
        if not self.confirmDiscardSlices():
            return
        if self.currentImageIndex > 0:
            self.currentImageIndex -= 1
            self.loadCurrentFolderImage()
        else:
            QApplication.beep()   # 已達第一張時發聲
            self.statusBar().showMessage("已是第一張")

    def openImage(self):
        path, _ = QFileDialog.getOpenFileName(self, "導入圖片", "", "Images (*.png *.jpg *.bmp)")
        if path:
            self.sliceView.loadImage(path)
            # 清空切片列表與顯示完整檔名
            self.sliceList.clear()
            filename = os.path.basename(path)
            self.statusBar().showMessage(f"載入圖片：{filename}")
            self.originalBaseName = os.path.splitext(filename)[0]
            self.currentImagePath = path  # 儲存圖片路徑
            self.checkAndLoadProject()     # 自動檢查工程文件

    def checkAndLoadProject(self):
        if self.currentImagePath:
            directory = os.path.dirname(self.currentImagePath)
            base = os.path.splitext(os.path.basename(self.currentImagePath))[0]
            proj_path = os.path.join(directory, base + ".cutter")
            if (os.path.exists(proj_path)):
                # 先移除現有切片（保留圖片項）
                for item in self.sliceView.scene().items():
                    if isinstance(item, SliceRect):
                        self.sliceView.scene().removeItem(item)
                with open(proj_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for i, l in enumerate(lines):
                        tmp = [float(j) for j in l.strip().split("\t")]
                        new_slice = SliceRect(QRectF(tmp[0], tmp[1], tmp[2], tmp[3]), i+1)
                        self.sliceView.scene().addItem(new_slice)
                self.updateSliceList()
                self.statusBar().showMessage(f"自動載入工程文件：{os.path.basename(proj_path)}")

    def writeProjectFile(self, file_path):
        slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        slices.sort(key=lambda s: s.number)
        # 將每個切片的數據以整數格式寫入，保留與狀態欄一致的精度
        projectData = "\n".join([
            "\t".join([
                str(int(item.rect().x())),
                str(int(item.rect().y())),
                str(int(item.rect().width())),
                str(int(item.rect().height()))
            ]) for item in slices
        ])
        if not projectData.strip():
            # 工程數據爲空，刪除文件以避免冗餘
            if os.path.exists(file_path):
                os.remove(file_path)
            self.statusBar().showMessage("工程已保存：無切片數據，空工程文件已刪除")
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(projectData)
            QApplication.beep()  # 保存後發聲提示
            self.statusBar().showMessage(f"工程已保存：{file_path}")

    def saveProject(self):
        if not self.currentImagePath:
            self.statusBar().showMessage("請先導入圖片")
            return
        directory = os.path.dirname(self.currentImagePath)
        base = os.path.splitext(os.path.basename(self.currentImagePath))[0]
        file_path = os.path.join(directory, base + ".cutter")
        self.writeProjectFile(file_path)
        self.clearProjectEdited()

    def saveProjectAs(self):
        if not self.currentImagePath:
            self.statusBar().showMessage("請先導入圖片")
            return
        directory = os.path.dirname(self.currentImagePath)
        base = os.path.splitext(os.path.basename(self.currentImagePath))[0]
        default_name = base + ".cutter"
        file_path, _ = QFileDialog.getSaveFileName(self, "工程另存爲", os.path.join(directory, default_name), "工程文件 (*.cutter)")
        if file_path:
            if not file_path.endswith(".cutter"):
                file_path += ".cutter"
            self.writeProjectFile(file_path)
            self.clearProjectEdited()

    def exportSlices(self):
        if not self.sliceView.image_item:
            self.statusBar().showMessage("請先導入圖片")
            return
        # 若有預設導出目錄與格式，則直接使用，不再彈窗
        if self.defaultExportDir and self.defaultExportFormat:
            export_dir = self.defaultExportDir
            fmt = self.defaultExportFormat
        else:
            export_dir = QFileDialog.getExistingDirectory(self, "選擇導出目錄", "")
            if not export_dir:
                return
            formats = ["PNG", "JPG", "BMP"]
            try:
                current_index = formats.index(self.defaultExportFormat)
            except ValueError:
                current_index = 0
            fmt, ok = QInputDialog.getItem(self, "選擇格式", "導出格式:", formats, current_index, False)
            if not ok:
                return
        original = self.sliceView.image_item.pixmap().toImage()
        base = getattr(self, "originalBaseName", "IMAGE")
        slices = [item for item in self.sliceView.scene().items() if isinstance(item, SliceRect)]
        slices.sort(key=lambda s: s.number)
        for idx, item in enumerate(slices, start=1):
            rect = item.rect().toRect()
            cropped = original.copy(rect)
            file_name = f"{base}_{idx:03d}.{fmt.lower()}"
            file_path = os.path.join(export_dir, file_name)
            cropped.save(file_path, fmt)
        QApplication.beep()   # 導出成功後發出系統聲音提示
        self.statusBar().showMessage(f"導出完成, 輸出目錄：{export_dir}")

    def showAbout(self):
        QMessageBox.about(self, "關於", "囫圇切 HulenCut v0.5\n\n左鍵拖拽創建切片，雙擊選擇切片，或在列表中選擇。\n按住 Ctrl 以在視圖中進行 單擊/拖拽 以多選。\n右鍵切片以刪除，或在列表中 右鍵/Delete 鍵刪除。\n雙擊後按住左鍵拖拽移動切片，也可用方向鍵移動。\n當指定了切片固定長寬時不支持雙擊操作。\n\n鳴謝：\nGithub Copilot\nBasic 低手\n\n活字攷古 @hulenkius 絕讚狗啃中")

    def openProject(self):
        path, _ = QFileDialog.getOpenFileName(self, "導入工程", "", "工程文件 (*.cutter)")
        if path:
            # 刪除現有切片項目（保留圖片）
            for item in self.sliceView.scene().items():
                if isinstance(item, SliceRect):
                    self.sliceView.scene().removeItem(item)
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for i, l in enumerate(lines):
                    tmp = [float(j) for j in l.strip().split("\t")]
                    new_slice = SliceRect(QRectF(tmp[0], tmp[1], tmp[2], tmp[3]), i+1)
                    self.sliceView.scene().addItem(new_slice)
            self.updateSliceList()
            self.statusBar().showMessage(f"已載入工程：{os.path.basename(path)}")
            self.markProjectEdited()

    # 清空切片的槽函數
    def clearAllSlices(self):
        scene = self.sliceView.scene()
        for item in scene.items():
            if isinstance(item, SliceRect):
                scene.removeItem(item)
        self.updateSliceList()
        if hasattr(self, "statusBar"):
            self.statusBar().showMessage("所有切片已清空")
        if hasattr(self, "markProjectEdited"):
            self.markProjectEdited()

    # 移動切片功能
    def openMoveSlicesDialog(self):
        dlg = MoveSlicesDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            target, dx, dy = dlg.getValues()
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
            self.statusBar().showMessage("切片移動完成")
            self.markProjectEdited()

    # 縮放切片功能
    def openScaleSlicesDialog(self):
        dlg = ScaleSlicesDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            target, scaleX, scaleY = dlg.getValues()
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
            self.statusBar().showMessage("切片縮放完成")
            self.markProjectEdited()

    def importKandianJson(self):
        # 檢查當前是否有處理的圖片
        if not self.currentImagePath:
            QApplication.beep()
            self.statusBar().showMessage("請先導入圖片")
            return

        json_path, _ = QFileDialog.getOpenFileName(self, "選擇看典古籍json", "", "JSON 文件 (*.json)")
        if not json_path:
            return

        # 讀取看典古籍json數據並轉換
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.statusBar().showMessage(f"錯誤：讀取json失敗：{e}")
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
                    if (rect):
                        slices.append({
                            "number": slice_index,
                            "rect": list(rect)
                        })
                        slice_index += 1
                        has_valid = True
                # 若 words 資料存在但均無位置信息，則退回使用整行信息
                if has_valid:
                    continue
            # 使用整行的 position 數據
            pts = line.get("position", [])
            rect = computeRect(pts)
            if (rect):
                slices.append({
                    "number": slice_index,
                    "rect": list(rect)
                })
                slice_index += 1

        # 生成同名的 .cutter 工程文件
        cutterfn = os.path.splitext(json_path)[0] + ".cutter"
        project = {
            "image": self.currentImagePath,
            "slices": slices
        }
        try:
            with open(cutterfn, 'w', encoding='utf-8') as f:
                json.dump(project, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.statusBar().showMessage(f"錯誤：寫入工程文件失敗：{e}")
            return

        # 清空現有切片（保留圖片項）
        scene = self.sliceView.scene()
        for item in list(scene.items()):
            if isinstance(item, SliceRect):
                scene.removeItem(item)

        # 根據轉換後數據新增切片
        for s in slices:
            rect_values = s["rect"]
            from PyQt5.QtCore import QRectF
            new_slice = SliceRect(QRectF(*rect_values), s["number"])
            scene.addItem(new_slice)

        # 在顯示成功導入訊息前，覆寫當前切片列表工程至 cutterfn 文件
        self.writeProjectFile(cutterfn)
        
        self.updateSliceList()
        self.statusBar().showMessage(f"成功轉換並導入工程文件：{cutterfn}")
        self.markProjectEdited()

    # 篩選切片功能
    def filterSlices(self):
        dlg = FilterSlicesDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            target, condition, threshold = dlg.getValues()
            # 選定要處理的切片
            if target == "all":
                slices = [s for s in self.sliceView.scene().items() if isinstance(s, SliceRect)]
            else:
                slices = [s for s in self.sliceList.selectedItems() if s.data(Qt.UserRole)]
                slices = [s.data(Qt.UserRole) for s in slices]
            # 根據條件移除切片：小於or大於閾值
            for s in slices:
                w = s.rect().width()
                h = s.rect().height()
                if condition == "lt" and w < threshold and h < threshold:
                    self.sliceView.scene().removeItem(s)
                elif condition == "gt" and w > threshold and h > threshold:
                    self.sliceView.scene().removeItem(s)
            self.updateSliceList()
            self.statusBar().showMessage("切片篩選完成")
            self.markProjectEdited()

    # 打開劃分切片對話框
    def openDivideSlicesDialog(self):
        dialog = DivideSlicesDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            cols, rows, method = dialog.getValues()
            self.divide_params = (cols, rows, method)
            self.dividingSlices = True
            self.dividePoints = []
            self.statusBar().showMessage("劃分切片：請點選第一個點")

    # 處理劃分切片
    def divideSlices(self):
        if not self.divide_params or len(self.dividePoints) < 2:
            return
        cols, rows, method = self.divide_params
        p1, p2 = self.dividePoints[0], self.dividePoints[1]
        scene = self.sliceView.scene()
        items = []
        if method == "corner":
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
        else:  # center method
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
        self.statusBar().showMessage("劃分切片完成")
        if hasattr(self, "markProjectEdited"):
            self.markProjectEdited()

    # 新增標記方法
    def markProjectEdited(self):
        self.projectEdited = True

    def clearProjectEdited(self):
        self.projectEdited = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    from PyQt5.QtGui import QFont
    app.setFont(QFont("MS Gothic", 10))
    app.setWindowIcon(QIcon(resource_path("hulencutter.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
