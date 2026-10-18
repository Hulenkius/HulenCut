"""Graphics scene, slice items, and list widgets."""

from PyQt5.QtCore import QLineF, QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPalette, QPen, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QInputDialog,
    QListWidget,
    QMenu,
    QMessageBox,
    QStyle,
    QStyledItemDelegate,
)

from .i18n import tr


class SliceRect(QGraphicsRectItem):
    lastSelected = None
    # 內部 ResizeHandle 類別
    class ResizeHandle(QGraphicsEllipseItem):
        def __init__(self, posKey, parentSlice):
            super().__init__(parentSlice)
            self.posKey = posKey
            self.parentSlice = parentSlice
            # 根據手柄位置設定合適的游標
            cursors = {
                "top_left": Qt.SizeFDiagCursor,
                "top": Qt.SizeVerCursor,
                "top_right": Qt.SizeBDiagCursor,
                "right": Qt.SizeHorCursor,
                "bottom_right": Qt.SizeFDiagCursor,
                "bottom": Qt.SizeVerCursor,
                "bottom_left": Qt.SizeBDiagCursor,
                "left": Qt.SizeHorCursor
            }
            self.setCursor(cursors.get(posKey, Qt.ArrowCursor))
            self.setAcceptedMouseButtons(Qt.LeftButton)
            self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)

        def mousePressEvent(self, event):
            self.startPos = event.scenePos()
            self.startRect = self.parentSlice.rect()
            event.accept()

        def mouseMoveEvent(self, event):
            delta = event.scenePos() - self.startPos
            r = QRectF(self.startRect)
            if self.posKey == "top_left":
                r.setTopLeft(r.topLeft() + delta)
            elif self.posKey == "top":
                r.setTop(r.top() + delta.y())
            elif self.posKey == "top_right":
                r.setTopRight(r.topRight() + delta)
            elif self.posKey == "right":
                r.setRight(r.right() + delta.x())
            elif self.posKey == "bottom_right":
                r.setBottomRight(r.bottomRight() + delta)
            elif self.posKey == "bottom":
                r.setBottom(r.bottom() + delta.y())
            elif self.posKey == "bottom_left":
                r.setBottomLeft(r.bottomLeft() + delta)
            elif self.posKey == "left":
                r.setLeft(r.left() + delta.x())
            # 防止尺寸過小
            if r.width() < 5 or r.height() < 5:
                r = self.parentSlice.rect()
            self.parentSlice.setRect(r)
            self.parentSlice.updateHandles()
            event.accept()

        def mouseReleaseEvent(self, event):
            event.accept()
            # 更新切片列表，保證切片邊緣調整後數據即時更新
            scene = self.parentSlice.scene()
            if scene and scene.views():
                main = scene.views()[0].parent()
                if hasattr(main, "updateSliceList"):
                    main.updateSliceList()

    def __init__(self, rect, number, *args, name="", **kwargs):
        super().__init__(rect, *args, **kwargs)
        self.number = number
        self.name = name
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
        self.createHandles()

    def createHandles(self):
        handlePositions = ["top_left", "top", "top_right", "right",
                           "bottom_right", "bottom", "bottom_left", "left"]
        self.handles = {}
        for pos in handlePositions:
            handle = SliceRect.ResizeHandle(pos, self)
            handle.setRect(0, 0, 8, 8)  # 手柄大小 8x8
            handle.setBrush(QColor("#ffffff"))
            handle.setPen(QPen(QColor("#2680eb"), 1.4))
            handle.setZValue(100)
            handle.hide()
            self.handles[pos] = handle
        self.updateHandles()

    def updateHandles(self):
        r = self.rect()
        cx, cy = r.center().x(), r.center().y()
        positions = {
            "top_left": QPointF(r.left(), r.top()),
            "top": QPointF(cx, r.top()),
            "top_right": QPointF(r.right(), r.top()),
            "right": QPointF(r.right(), cy),
            "bottom_right": QPointF(r.right(), r.bottom()),
            "bottom": QPointF(cx, r.bottom()),
            "bottom_left": QPointF(r.left(), r.bottom()),
            "left": QPointF(r.left(), cy)
        }
        for key, handle in self.handles.items():
            handle.setPos(positions[key] - QPointF(4, 4))  # 平移使手柄置中

    def setSelected(self, selected):
        super().setSelected(selected)
        fixedMode = getattr(self.scene().views()[0].parent(), "fixedSliceSize", None) if self.scene() and self.scene().views() else None
        if selected:
            if SliceRect.lastSelected and SliceRect.lastSelected != self:
                for handle in SliceRect.lastSelected.handles.values():
                    try:
                        handle.hide()
                    except RuntimeError:
                        pass
            SliceRect.lastSelected = self
            for handle in self.handles.values():
                try:
                    handle.setVisible(fixedMode is None)
                except RuntimeError:
                    pass
            self.updateHandles()
        else:
            for handle in self.handles.values():
                try:
                    handle.hide()
                except RuntimeError:
                    pass
            if SliceRect.lastSelected == self:
                SliceRect.lastSelected = None

    def mousePressEvent(self, event):
        self.setSelected(True)
        self._mousePressScenePos = event.scenePos()
        # 多選拖拽：記錄所有已選切片的初始矩形
        selected = [it for it in self.scene().selectedItems() if isinstance(it, SliceRect)]
        if len(selected) > 1:
            self._groupInitialRects = {s: QRectF(s.rect()) for s in selected}
        else:
            self._groupInitialRects = None
        self._initialPos = self.pos()
        if self.scene() and self.scene().views():
            parent = self.scene().views()[0].parent()
            if hasattr(parent, "statusBar"):
                parent.statusBar().showMessage(tr('切片 {0} 移動中').format(self.number))
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        # 處理多選切片一起拖拽
        if getattr(self, "_groupInitialRects", None):
            delta = event.scenePos() - self._mousePressScenePos
            for s, orig in self._groupInitialRects.items():
                new_rect = orig.translated(delta)
                s.setRect(new_rect)
                s.updateHandles()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # 多選拖拽完成後更新列表
        if getattr(self, "_groupInitialRects", None):
            self._groupInitialRects = None
            if self.scene() and self.scene().views():
                main = self.scene().views()[0].parent()
                if hasattr(main, "updateSliceList"):
                    main.updateSliceList()
                if hasattr(main, "markProjectEdited"):
                    main.markProjectEdited()
            return
        delta = event.scenePos() - self._mousePressScenePos
        if delta.manhattanLength() < 5:
            self.setPos(self._initialPos)
            if self.scene() and self.scene().views():
                parent = self.scene().views()[0].parent()
                if hasattr(parent, "statusBar"):
                    rect = self.rect()
                    x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
                    name_msg = f" | {self.name}" if self.name else ""
                    parent.statusBar().showMessage(tr('已選擇：切片 {0}{1}（X:{2} Y:{3} 寬:{4} 高:{5}）').format(self.number, name_msg, x, y, w, h))
        else:
            if self.scene() and self.scene().views():
                parent = self.scene().views()[0].parent()
                if hasattr(parent, "statusBar"):
                    parent.statusBar().showMessage(tr('切片 {0} 移動完成').format(self.number))
            moved_offset = self.pos() - self._initialPos
            new_rect = self.rect().translated(moved_offset)
            self.setRect(new_rect)
            self.updateHandles()
            self.setPos(self._initialPos)
            if self.scene() and self.scene().views():
                main = self.scene().views()[0].parent()
                if hasattr(main, "updateSliceList"):
                    main.updateSliceList()
                if hasattr(main, "markProjectEdited"):
                    main.markProjectEdited()
            # 新增脚本記錄
            if hasattr(main, "recorder"):
                selected = [it for it in self.scene().selectedItems() if isinstance(it, SliceRect)]
                if selected:
                    if len(selected) == 1:
                        main.recorder.log_action("moveSliceByMouse", selected[0].number, int(moved_offset.x()), int(moved_offset.y()))
                    else:
                        nums = ",".join(str(s.number) for s in selected)
                        main.recorder.log_action("moveSlicesByMouse", nums, int(moved_offset.x()), int(moved_offset.y()))
        
    def labelsVisible(self) -> bool:
        """Overlays disappear while selected so handles stay unobstructed."""
        return not self.isSelected()

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self.isSelected():
            accent = QColor("#2680eb")
            painter.fillRect(self.rect(), QColor(38, 128, 235, 40))
            pen = QPen(accent, 2.2)
        else:
            accent = QColor(38, 128, 235, 190)
            pen = QPen(accent, 1.4)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect())

        # Photoshop-like overlays are hidden while selected so they never
        # cover the resize handles or interfere with fine adjustment.
        if self.labelsVisible():
            if self.number and self.rect().width() > 24:
                label = str(self.number)
                font = QFont(QApplication.font())
                font.setPointSize(8)
                font.setBold(True)
                painter.setFont(font)
                metrics = QFontMetricsF(font)
                badge_width = max(18.0, metrics.horizontalAdvance(label) + 9.0)
                badge = QRectF(self.rect().left() + 3, self.rect().top() + 3, badge_width, 15)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#2680eb"))
                painter.drawRoundedRect(badge, 4, 4)
                painter.setPen(QColor("#ffffff"))
                painter.drawText(badge, Qt.AlignCenter, label)

            if self.name and self.rect().width() > 36:
                font = QFont(QApplication.font())
                font.setPointSize(8)
                painter.setFont(font)
                metrics = QFontMetricsF(font)
                available_width = max(20.0, min(140.0, self.rect().width() - 12))
                label = metrics.elidedText(self.name, Qt.ElideRight, int(available_width - 10))
                name_width = min(available_width, metrics.horizontalAdvance(label) + 10.0)
                badge = QRectF(
                    self.rect().right() - name_width - 3,
                    self.rect().bottom() - 18,
                    name_width,
                    15,
                )
                painter.setPen(QPen(QColor(255, 255, 255, 45), 1))
                painter.setBrush(QColor(20, 20, 20, 200))
                painter.drawRoundedRect(badge, 4, 4)
                painter.setPen(QColor("#f2f2f2"))
                painter.drawText(badge, Qt.AlignCenter, label)

    def contextMenuEvent(self, event):
        menu = QMenu()
        renameAct = menu.addAction(tr("重命名切片"))
        deleteAct = menu.addAction(tr("刪除切片"))
        action = menu.exec_(event.screenPos())
        if action == renameAct:
            from PyQt5.QtWidgets import QInputDialog, QMessageBox
            newName, ok = QInputDialog.getText(self.scene().views()[0].parent(), tr("重命名"), tr("請輸入新名稱："), text=self.name)
            if ok:
                import re
                if re.search(r'[<>*?/\\]', newName):
                    QMessageBox.warning(self.scene().views()[0].parent(), tr("錯誤"), tr("名稱包含非法字符"))
                else:
                    self.name = newName.strip()
                    main = self.scene().views()[0].parent()
                    main.statusBar().showMessage(tr('已重命名切片 {0}').format(self.number) + (tr(' 爲: {0}').format(self.name) if self.name else ""))
                    if hasattr(main, "updateSliceList"):
                        main.updateSliceList()
                    if hasattr(main, "markProjectEdited"):
                        main.markProjectEdited()
            event.accept()
        elif action == deleteAct:
            if self.scene() and self.scene().views():
                parent = self.scene().views()[0].parent()
                if hasattr(parent, "statusBar"):
                    parent.statusBar().showMessage(tr("已刪除選定切片"))
                if hasattr(parent, "markProjectEdited"):
                    parent.markProjectEdited()
            scene = self.scene()
            scene.removeItem(self)
            scene.update()
            if scene and scene.views():
                view = scene.views()[0]
                if hasattr(view.parent(), "updateSliceList"):
                    view.parent().updateSliceList()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange and self.scene():
            views = self.scene().views()
            main = views[0].parent() if views else None
            if value and main is not None and getattr(main, "fixedSliceSize", None) is None:
                if len([item for item in self.scene().selectedItems() if isinstance(item, SliceRect)]) == 1:
                    pass
                else:
                    pass
            else:
                pass
        return super().itemChange(change, value)


class SliceView(QGraphicsView):
    def __init__(self, parent):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.mainWindow = parent
        self.setAcceptDrops(True)
        self.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing
        )
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._dropActive = False
        # 允許接收鍵盤焦點，確保方向鍵等事件能持續被接收
        self.setFocusPolicy(Qt.StrongFocus)
        self.image_item = None
        self.drawing = False
        self.fixedMode = False
        self.start_pos = QPointF()
        self.tempRect = None
        self.selecting = False
        self.startSelectPos = QPointF()
        self.rubberRect = None
        self.panning = False
        self.panning = False  # 新增：空格拖拽標誌
        self.setMouseTracking(True)
        # 記錄是否開始拖拽
        self.selectionDragStarted = False
        # 標尺設定
        self.showRulers = True
        self.rulerSize = 20
        self.rulerOpaque = True
        # 滾動時刷新標尺
        self.horizontalScrollBar().valueChanged.connect(self.viewport().update)
        self.verticalScrollBar().valueChanged.connect(self.viewport().update)

    def _rect_from_origin(self, pt: QPointF, w: float, h: float, origin: str) -> QRectF:
        # 根據原點 key 與點位計算 QRectF
        x = pt.x()
        y = pt.y()
        if origin == "top_left":
            rx = x
            ry = y
        elif origin == "top":
            rx = x - w/2
            ry = y
        elif origin == "top_right":
            rx = x - w
            ry = y
        elif origin == "left":
            rx = x
            ry = y - h/2
        elif origin == "center":
            rx = x - w/2
            ry = y - h/2
        elif origin == "right":
            rx = x - w
            ry = y - h/2
        elif origin == "bottom_left":
            rx = x
            ry = y - h
        elif origin == "bottom":
            rx = x - w/2
            ry = y - h
        elif origin == "bottom_right":
            rx = x - w
            ry = y - h
        else:
            rx = x - w/2
            ry = y - h/2
        return QRectF(rx, ry, w, h)

    def loadImage(self, image_path):
        pixmap = QPixmap(image_path)
        self.scene().clear()
        self.scene().setSceneRect(QRectF(pixmap.rect()))
        self.image_item = self.scene().addPixmap(pixmap)
        
    def mousePressEvent(self, event):
        # 若尚未載入圖片，則不允許任何切片創建／繪製行為
        if self.image_item is None:
            super().mousePressEvent(event)
            return
        # 空格拖拽：開始 panning（攔截所有其它互動）
        if self.panning and event.button() == Qt.LeftButton:
            self._pan_start = event.pos()
            self._initial_hbar = self.horizontalScrollBar().value()
            self._initial_vbar = self.verticalScrollBar().value()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        # 裁剪模式下：只允許直接拖動裁剪框的手柄，其它操作屏蔽
        if self.mainWindow.croppingMode:
            item = self.scene().itemAt(self.mapToScene(event.pos()), self.transform())
            # 若點擊的是 ResizeHandle，交給父類處理以觸發調整
            if isinstance(item, SliceRect.ResizeHandle):
                super().mousePressEvent(event)
                return
            event.accept()
            return
        # 如果已在拉直預覽階段，阻止任何視圖內點擊（不建新切片）
        if self.mainWindow.straightenPreviewActive:
            event.accept()
            return
        # 直線校正優先
        if event.button()==Qt.LeftButton and self.mainWindow.straighteningMode:
            pt = self.mapToScene(event.pos())
            main = self.mainWindow
            main.straightenPoints.append(pt)
            # 移除舊線
            if main.tempStraightenLine and main.tempStraightenLine.scene():
                self.scene().removeItem(main.tempStraightenLine)
            main.tempStraightenLine = QGraphicsLineItem(QLineF(pt,pt))
            main.tempStraightenLine.setPen(QPen(Qt.blue,4,Qt.DashLine))
            self.scene().addItem(main.tempStraightenLine)
            event.accept(); return
        # 優先處理劃分切片模式
        if event.button() == Qt.LeftButton and hasattr(self.parent(), "dividingSlices") and self.parent().dividingSlices:
            pt = self.mapToScene(event.pos())
            mainw = self.parent()
            mainw.dividePoints.append(pt)
            if len(mainw.dividePoints) == 1:
                mainw.statusBar().showMessage(tr("劃分切片：請點選第二個點"))
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
                # 取得鼠標點（依所選原點定位）
                click_pt = self.mapToScene(event.pos())
                self.fixedWidth, self.fixedHeight = fixedSize
                origin = getattr(self.parent(), "fixedSliceOrigin", "center")
                rect = self._rect_from_origin(click_pt, self.fixedWidth, self.fixedHeight, origin)
                self.tempRect = self.scene().addRect(rect, QPen(Qt.green, 2, Qt.DashLine))
                # 儲存目前原點以備更新時使用
                self._currentFixedOrigin = origin
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
        # 空格拖拽：滾動視圖
        if self.panning and hasattr(self, '_pan_start'):
            delta = event.pos() - self._pan_start
            self.horizontalScrollBar().setValue(self._initial_hbar - delta.x())
            self.verticalScrollBar().setValue(self._initial_vbar - delta.y())
            event.accept()
            return
        # 標尺半透明切換
        if self.showRulers:
            pos = event.pos()  # viewport 座標
            self.rulerOpaque = not (pos.x() < self.rulerSize or pos.y() < self.rulerSize)
            self.viewport().update()
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
            # 更新虛線框，使鼠標依選定原點定位
            new_pt = self.mapToScene(event.pos())
            origin = getattr(self.parent(), "fixedSliceOrigin", getattr(self, '_currentFixedOrigin', 'center'))
            rect = self._rect_from_origin(new_pt, self.fixedWidth, self.fixedHeight, origin)
            self.tempRect.setRect(rect)
        elif self.drawing and self.tempRect is not None:
            current_pos = self.mapToScene(event.pos())
            rect = QRectF(self.start_pos, current_pos).normalized()
            self.tempRect.setRect(rect)
        elif self.mainWindow.straighteningMode and self.mainWindow.tempStraightenLine:
            curr = self.mapToScene(event.pos())
            line = self.mainWindow.tempStraightenLine.line()
            line.setP2(curr)
            self.mainWindow.tempStraightenLine.setLine(line)
            event.accept(); return
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # 若尚未載入圖片，則不允許任何切片創建／繪製行為
        if self.image_item is None:
            super().mouseReleaseEvent(event)
            return
        # 空格拖拽結束
        if self.panning and event.button() == Qt.LeftButton and hasattr(self, '_pan_start'):
            del self._pan_start, self._initial_hbar, self._initial_vbar
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return
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
            # 同步列表選中剛創建的切片並刷新預覽
            lw = self.parent().sliceList
            if lw.count() > 0:
                lw.clearSelection()
                lw.setCurrentRow(lw.count()-1)
                lw.item(lw.count()-1).setSelected(True)
                # 新建切片後將鍵盤焦點回到視圖，讓方向鍵可直接生效
                try:
                    self.setFocus()
                except Exception:
                    pass
            if hasattr(self.parent(), "update_preview_panel"):
                self.parent().update_preview_panel()
            if hasattr(self.parent(), "statusBar"):
                x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
                self.parent().statusBar().showMessage(tr('創建成功：切片 {0}（{1},{2} | {3}x{4}）').format(new_slice.number, x, y, w, h))
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
            # 同步列表選中剛創建的切片並刷新預覽
            lw = self.parent().sliceList
            if lw.count() > 0:
                lw.clearSelection()
                lw.setCurrentRow(lw.count()-1)
                lw.item(lw.count()-1).setSelected(True)
            if hasattr(self.parent(), "update_preview_panel"):
                self.parent().update_preview_panel()
            if hasattr(self.parent(), "statusBar"):
                x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
                self.parent().statusBar().showMessage(tr('創建成功：切片 {0}（{1},{2} | {3}x{4}）').format(new_slice.number, x, y, w, h))
            if hasattr(self.parent(), "markProjectEdited"):
                self.parent().markProjectEdited()
            # 確保視圖保持焦點
            try:
                self.setFocus()
            except Exception:
                pass
        # 完成直線校正：預覽
        if event.button()==Qt.LeftButton and self.mainWindow.straighteningMode:
            self.mainWindow.straighteningMode=False
            p1 = self.mainWindow.tempStraightenLine.line().p1()
            p2 = self.mainWindow.tempStraightenLine.line().p2()
            # 移除線條
            if self.mainWindow.tempStraightenLine.scene():
                self.scene().removeItem(self.mainWindow.tempStraightenLine)
            self.mainWindow.tempStraightenLine=None
            self.mainWindow.previewStraighten(p1,p2)
            event.accept(); return
        else:
            super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.NoDrag)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.image_item is None:
            self._paint_empty_state()
            return
        if not getattr(self, 'showRulers', False):
            return
        painter = QPainter(self.viewport())
        painter.setOpacity(1.0 if self.rulerOpaque else 0.5)
        palette = self.palette()
        ruler_bg = palette.button().color()
        ruler_line = palette.mid().color()
        ruler_text = palette.text().color()
        line_pen = QPen(ruler_line, 1)
        text_pen = QPen(ruler_text, 1)
        painter.setPen(line_pen)
        # Ruler text follows the active language font (JhengHei / YaHei / Segoe UI).
        painter.setFont(self.font())

        scale = self.transform().m11()
        hbar = self.horizontalScrollBar().value()
        vbar = self.verticalScrollBar().value()
        vw = self.viewport().width()
        vh = self.viewport().height()

        # 計算步長
        desired_px = 50
        nice_steps = [1,2,5,10,20,50,100,200,500,1000]
        data_step = nice_steps[-1]
        for u in nice_steps:
            if u * scale >= desired_px:
                data_step = u
                break
        step = data_step * scale

        # 水平標尺
        painter.fillRect(0, 0, vw, self.rulerSize, ruler_bg)
        x0 = - (hbar % step)
        while x0 < vw:
            real = int((x0 + hbar) / scale)
            painter.setPen(line_pen)
            painter.drawLine(int(x0), self.rulerSize, int(x0), 0)
            painter.setPen(text_pen)
            painter.drawText(int(x0 + 2), self.rulerSize - 7, str(real))
            x0 += step

        # 垂直標尺
        painter.fillRect(0, 0, self.rulerSize, vh, ruler_bg)
        y0 = - (vbar % step)
        while y0 < vh:
            real = int((y0 + vbar) / scale)
            painter.setPen(line_pen)
            painter.drawLine(self.rulerSize, int(y0), 0, int(y0))
            painter.save()
            painter.translate(self.rulerSize - 7, int(y0 + 2) - 3)  # 上移3px，防止文本貼近刻度線
            painter.rotate(-90)
            # Keep vertical ruler text on the same active UI font.
            painter.setFont(self.font())
            painter.setPen(text_pen)
            painter.drawText(0, 0, str(real))
            painter.restore()
            y0 += step

        painter.end()

    def _paint_empty_state(self):
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = self.palette()
        vw, vh = self.viewport().width(), self.viewport().height()

        dot = QColor(palette.mid().color())
        dot.setAlpha(30)
        painter.setPen(QPen(dot, 1))
        for x in range(18, vw, 28):
            for y in range(18, vh, 28):
                painter.drawPoint(x, y)

        card_width = min(560, max(360, vw - 120))
        card_height = 236
        card = QRectF((vw - card_width) / 2, (vh - card_height) / 2, card_width, card_height)
        border = QColor(palette.highlight().color() if self._dropActive else palette.mid().color())
        border.setAlpha(220 if self._dropActive else 95)
        card_bg = QColor(palette.base().color())
        card_bg.setAlpha(246)
        painter.setPen(QPen(border, 2 if self._dropActive else 1))
        painter.setBrush(card_bg)
        painter.drawRoundedRect(card, 18, 18)

        accent = palette.highlight().color()
        icon_size = 46
        icon_rect = QRectF(card.center().x() - icon_size / 2, card.top() + 24, icon_size, icon_size)
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(icon_rect)
        painter.setPen(QColor("#ffffff"))
        icon_font = QFont(self.font())
        icon_font.setPointSize(20)
        icon_font.setBold(True)
        painter.setFont(icon_font)
        painter.drawText(icon_rect, Qt.AlignCenter, "+")

        title = tr("放開以導入") if self._dropActive else tr("拖入圖片或文件夾開始")
        painter.setPen(palette.text().color())
        title_font = QFont(self.font())
        title_font.setPointSize(15)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(card.left() + 24, icon_rect.bottom() + 14, card.width() - 48, 32),
            Qt.AlignHCenter | Qt.AlignVCenter,
            title,
        )

        hint_font = QFont(self.font())
        hint_font.setPointSize(10)
        painter.setFont(hint_font)
        muted = palette.mid().color()
        painter.setPen(muted)
        painter.drawText(
            QRectF(card.left() + 24, icon_rect.bottom() + 52, card.width() - 48, 26),
            Qt.AlignHCenter | Qt.AlignVCenter,
            tr("支援圖片與 HulenCut 工程文件"),
        )
        painter.setPen(QColor(accent))
        painter.drawText(
            QRectF(card.left() + 24, icon_rect.bottom() + 82, card.width() - 48, 26),
            Qt.AlignHCenter | Qt.AlignVCenter,
            tr("也可以按 Ctrl+O 導入圖片"),
        )
        painter.end()

    @staticmethod
    def _event_has_local_urls(event) -> bool:
        mime = event.mimeData()
        return bool(mime and mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()))

    def dragEnterEvent(self, event):
        if self._event_has_local_urls(event):
            self._dropActive = True
            self.viewport().update()
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._event_has_local_urls(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._dropActive = False
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        if self._event_has_local_urls(event):
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
            self._dropActive = False
            self.viewport().update()
            if hasattr(self.mainWindow, "handleDroppedPaths"):
                self.mainWindow.handleDroppedPaths(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def keyPressEvent(self, event):
        # 新增：按下空格啓動拖拽
        if event.key() == Qt.Key_Space:
            self.panning = True
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(Qt.OpenHandCursor)
            return
        # 在裁剪模式下屏蔽按鍵操作
        if self.mainWindow.croppingMode:
            return
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
                self.parent().statusBar().showMessage(tr("已刪除選定切片"))
                pass
            if hasattr(self.parent(), "markProjectEdited"):
                self.parent().markProjectEdited()
                pass
            return
        # 處理方向鍵移動
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = 10 if event.modifiers() & Qt.ShiftModifier else 1
            dx = -step if event.key() == Qt.Key_Left else (step if event.key() == Qt.Key_Right else 0)
            dy = -step if event.key() == Qt.Key_Up   else (step if event.key() == Qt.Key_Down  else 0)
            # 直接平移 rect 而非 moveBy，確保 rect.x/y 更新
            for item in self.scene().selectedItems():
                if isinstance(item, SliceRect):
                    r = item.rect()
                    item.setRect(r.translated(dx, dy))
                    item.updateHandles()
            self.scene().update()
            # 更新列表與標記已編輯
            parent = self.parent()
            if hasattr(parent, "updateSliceList"):
                parent.updateSliceList()
            if hasattr(parent, "markProjectEdited"):
                parent.markProjectEdited()
            # 確保視圖保持焦點以接收後續方向鍵事件
            try:
                self.setFocus()
            except Exception:
                pass
            event.accept()
            return
            # 錄製脚本
            if hasattr(self.parent(), "recorder"):
                selected = [it for it in self.scene().selectedItems() if isinstance(it, SliceRect)]
                if selected:
                    if len(selected) == 1:
                        self.parent().recorder.log_action("moveSliceByKey", selected[0].number, dx, dy)
                    else:
                        nums = ",".join(str(s.number) for s in selected)
                        self.parent().recorder.log_action("moveSlicesByKey", nums, dx, dy)
            event.accept()
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

    def keyReleaseEvent(self, event):
        # 新增：鬆開空格恢復正常
        if event.key() == Qt.Key_Space:
            self.panning = False
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.ArrowCursor)
            return
        super().keyReleaseEvent(event)

    def zoomIn(self):
        self.scale(1.25, 1.25)
        # 同步更新主視窗的縮放比顯示
        if hasattr(self.mainWindow, "_updateZoomCombo"):
             self.mainWindow._updateZoomCombo()

    def zoomOut(self):
        self.scale(0.8, 0.8)
        # 同步更新主視窗的縮放比顯示
        if hasattr(self.mainWindow, "_updateZoomCombo"):
             self.mainWindow._updateZoomCombo()

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
             if event.angleDelta().y() > 0:
                 self.zoomIn()
             else:
                 self.zoomOut()
        else:
             super().wheelEvent(event)
            
    def leaveEvent(self, event):
        # 滑鼠離開主視圖時，標尺半透明
        if getattr(self, 'showRulers', False):
            self.rulerOpaque = False
            self.viewport().update()
        super().leaveEvent(event)


class SliceItemDelegate(QStyledItemDelegate):
    """Compact, table-like rendering for the slice list."""

    def sizeHint(self, option, index):
        height = max(26, option.fontMetrics.height() + 8)
        return QSize(0, height)

    def paint(self, painter, option, index):
        painter.save()
        painter.setClipRect(option.rect)
        painter.setRenderHint(QPainter.Antialiasing, True)

        slice_item = index.data(Qt.UserRole)
        palette = option.palette
        accent = palette.highlight().color()
        text_color = palette.text().color()
        muted = palette.mid().color()
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)

        row_rect = QRectF(option.rect)
        body_rect = row_rect.adjusted(1, 1, -1, -2)

        if index.row() % 2:
            alternate_bg = QColor(muted)
            alternate_bg.setAlpha(10)
            painter.fillRect(body_rect, alternate_bg)

        if selected:
            selected_bg = QColor(accent)
            selected_bg.setAlpha(38)
            painter.fillRect(body_rect, selected_bg)
        elif hovered:
            hover_bg = QColor(text_color)
            hover_bg.setAlpha(12)
            painter.fillRect(body_rect, hover_bg)

        if selected:
            marker = QRectF(body_rect.left() + 1, body_rect.top() + 3, 3, body_rect.height() - 6)
            painter.fillRect(marker, accent)

        number = getattr(slice_item, "number", 0) if slice_item else 0
        name = (getattr(slice_item, "name", "") or "").strip() if slice_item else ""
        rect = getattr(slice_item, "rect", lambda: QRectF())() if slice_item else QRectF()
        x, y = int(rect.x()), int(rect.y())
        width, height = int(rect.width()), int(rect.height())

        number_text = str(number) if number else ""
        number_font = QFont(option.font)
        number_font.setBold(True)
        painter.setFont(number_font)
        badge_width = max(24.0, painter.fontMetrics().horizontalAdvance(number_text) + 12.0)
        badge = QRectF(body_rect.left() + 8, body_rect.top() + 3, badge_width, body_rect.height() - 6)
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent if selected else QColor(muted.red(), muted.green(), muted.blue(), 80))
        painter.drawRoundedRect(badge, 3, 3)
        painter.setPen(QColor("#ffffff") if selected else text_color)
        painter.drawText(badge, Qt.AlignCenter, number_text)

        dims_text = f"X:{x}  Y:{y}  W:{width}  H:{height}" if slice_item else ""
        dims_font = QFont(option.font)
        if dims_font.pointSize() > 1:
            dims_font.setPointSize(dims_font.pointSize() - 1)
        painter.setFont(dims_font)
        dims_metrics = painter.fontMetrics()
        dims_width = dims_metrics.horizontalAdvance(dims_text) + 2
        dims_rect = QRectF(body_rect.right() - dims_width - 7, body_rect.top(), dims_width, body_rect.height())
        painter.setPen(muted)
        painter.drawText(dims_rect, Qt.AlignVCenter | Qt.AlignRight, dims_text)

        name_font = QFont(option.font)
        painter.setFont(name_font)
        name_rect = QRectF(
            badge.right() + 8,
            body_rect.top(),
            max(1.0, dims_rect.left() - badge.right() - 16),
            body_rect.height(),
        )
        display_name = name or ""
        if not name:
            painter.setPen(muted)
        else:
            painter.setPen(text_color)
        display_name = painter.fontMetrics().elidedText(display_name, Qt.ElideRight, int(name_rect.width()))
        painter.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, display_name)

        separator = QColor(muted)
        separator.setAlpha(55)
        painter.setPen(QPen(separator, 1))
        painter.drawLine(QPointF(body_rect.left(), body_rect.bottom() + 1), QPointF(body_rect.right(), body_rect.bottom() + 1))
        painter.restore()


class SliceListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sliceList")
        self.setItemDelegate(SliceItemDelegate(self))
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
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
        selected_items = self.selectedItems()
        if len(selected_items) == 1:
            renameAction = menu.addAction(tr("重命名切片"))
        clearNameAction = menu.addAction(tr("刪除名稱"))
        deleteAction = menu.addAction(tr("刪除切片"))
        action = menu.exec_(self.mapToGlobal(pos))
        if len(selected_items) == 1 and action == renameAction:
            item = selected_items[0]
            slice_item = item.data(Qt.UserRole)
            if slice_item:
                newName, ok = QInputDialog.getText(self, tr("重命名切片"), tr("請輸入新名稱："), text=slice_item.name)
                if ok:
                    import re
                    if re.search(r'[<>*?/\\]', newName):
                        QMessageBox.warning(self, tr("錯誤"), tr("名稱包含非法字符"))
                    else:
                        slice_item.name = newName.strip()
                        if self.window() and hasattr(self.window(), "statusBar"):
                            self.window().statusBar().showMessage(tr('已重命名切片 {0}').format(slice_item.number))
                        if hasattr(self.window(), "updateSliceList"):
                            self.window().updateSliceList()
                        if hasattr(self.window(), "markProjectEdited"):
                            self.window().markProjectEdited()
        elif action == clearNameAction:
            for item in selected_items:
                slice_item = item.data(Qt.UserRole)
                if slice_item:
                    slice_item.name = ""
            if self.window() and hasattr(self.window(), "updateSliceList"):
                self.window().updateSliceList()
            if self.window() and hasattr(self.window(), "statusBar"):
                self.window().statusBar().showMessage(tr("已清空選定切片名稱"))
            if self.window() and hasattr(self.window(), "markProjectEdited"):
                self.window().markProjectEdited()
        elif action == deleteAction:
            self.deleteSelectedItems()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.deleteSelectedItems()
        # 新增：處理上下方向鍵
        elif event.key() in (Qt.Key_Up, Qt.Key_Down):
            super().keyPressEvent(event)
            # 觸發後，將新選中的項目置中
            main_win = self.window()
            if main_win and hasattr(main_win, "sliceView"):
                selected = self.selectedItems()
                if len(selected) == 1:
                    slice_item = selected[0].data(Qt.UserRole)
                    if slice_item:
                        main_win.sliceView.centerOn(slice_item)
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
            main_win.statusBar().showMessage(tr("已刪除選定切片"))
        if hasattr(main_win, "markProjectEdited"):
            main_win.markProjectEdited()
