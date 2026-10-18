"""Dock panels and search / alignment helpers."""
import os
import unicodedata
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .graphics import SliceRect
from .i18n import tr
from .theme import theme_manager


class SliceDimensionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lblWidth = QLabel(tr("寬度:"))
        # 使用 QSpinBox：只允許正整數並帶有右側的上下按鈕
        self.spinWidth = QSpinBox()
        self.spinWidth.setRange(1, 10000)
        self.spinWidth.setSingleStep(1)
        self.spinWidth.setSuffix(" px")
        self.lblHeight = QLabel(tr("高度:"))
        self.spinHeight = QSpinBox()
        self.spinHeight.setRange(1, 10000)
        self.spinHeight.setSingleStep(1)
        self.spinHeight.setSuffix(" px")
        self.btnConfirm = QPushButton(tr("確定"))
        self.btnConfirm.clicked.connect(self.onConfirm)

        # 左側三行：寬度、長度、按鈕
        hLayout1 = QHBoxLayout()
        hLayout1.addWidget(self.lblWidth)
        hLayout1.addWidget(self.spinWidth)
        hLayout2 = QHBoxLayout()
        hLayout2.addWidget(self.lblHeight)
        hLayout2.addWidget(self.spinHeight)
        hbtnLayout = QHBoxLayout()
        hbtnLayout.addWidget(self.btnConfirm)

        # 右側：3x3 原點選項（左上, 中上, 右上 / 左中, 中心, 右中 / 左下, 中下, 右下）
        from PyQt5.QtWidgets import QRadioButton, QButtonGroup
        self.origin_buttons = {}
        self.origin_group = QButtonGroup(self)
        origin_names = [
            (tr("左上"), "top_left"), (tr("中上"), "top"), (tr("右上"), "top_right"),
            (tr("左中"), "left"),   (tr("中心"), "center"), (tr("右中"), "right"),
            (tr("左下"), "bottom_left"), (tr("中下"), "bottom"), (tr("右下"), "bottom_right")
        ]

        # 使用 Grid 來保證三行與左側三行縱向對齊
        rightGrid = QGridLayout()
        for idx, (labelText, key) in enumerate(origin_names):
            rb = QRadioButton(labelText, self)
            self.origin_buttons[key] = rb
            self.origin_group.addButton(rb, idx)
            # 當選擇變更時，立即更新主視窗的 fixedSliceOrigin
            rb.toggled.connect(lambda checked, k=key: self._onOriginToggled(k, checked))
            row = idx // 3
            col = idx % 3
            rightGrid.addWidget(rb, row, col)

        # 佈局：使用 Grid 把左側三行和右側三行對齊
        mainGrid = QGridLayout()
        mainGrid.addLayout(hLayout1, 0, 0)
        mainGrid.addLayout(hLayout2, 1, 0)
        mainGrid.addLayout(hbtnLayout, 2, 0)
        mainGrid.addLayout(rightGrid, 0, 1, 3, 1)
        self.setLayout(mainGrid)
        # 預設選中中心作為原點
        self.setFixedHeight(110)
        self.origin_buttons["center"].setChecked(True)
        
    def onConfirm(self):
        mainw = self.window()
        try:
            w = int(self.spinWidth.value())
            h = int(self.spinHeight.value())
        except Exception:
            mainw.statusBar().showMessage(tr("寬高數值無效"))
            return

        if getattr(mainw, 'fixedSliceSize', None) is None:
            # 進入定幅切片模式
            mainw.fixedSliceSize = (w, h)
            self.btnConfirm.setText(tr("退出定幅切片模式"))
            mainw.statusBar().showMessage(tr('已啓用定幅切片尺寸：{0} x {1}').format(w, h))
            # 禁用寬度/高度行與 spinbox（灰色且不可交互）
            try:
                self.lblWidth.setEnabled(False)
                self.spinWidth.setEnabled(False)
                self.lblHeight.setEnabled(False)
                self.spinHeight.setEnabled(False)
            except Exception:
                pass
        else:
            # 退出定幅切片模式（但不改變 spin 的值）
            mainw.fixedSliceSize = None
            self.btnConfirm.setText(tr("確定"))
            mainw.statusBar().showMessage(tr("已退出定幅切片模式"))
            # 還原寬度/高度行與 spinbox 可交互狀態
            try:
                self.lblWidth.setEnabled(True)
                self.spinWidth.setEnabled(True)
                self.lblHeight.setEnabled(True)
                self.spinHeight.setEnabled(True)
            except Exception:
                pass

    def _onOriginToggled(self, key, checked):
        # 當 radio 被選中時，更新主窗口的 fixedSliceOrigin
        if not checked:
            return
        try:
            self.window().fixedSliceOrigin = key
            # 顯示狀態反饋
            if hasattr(self.window(), 'statusBar'):
                self.window().statusBar().showMessage(tr('定幅切片原點：{0}').format(key))
        except Exception:
            pass


class StraightenWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
                # 垂直佈局：上排為「裁剪」，下排為「校正」
        layout = QVBoxLayout(self)
        layout.addStretch()
        # 第一行：裁剪按鈕
        h_crop = QHBoxLayout()
        self.btnCrop        = QPushButton(tr("裁剪"), self)
        self.btnConfirmCrop = QPushButton(tr("確認裁剪"), self)
        self.btnCancelCrop  = QPushButton(tr("取消裁剪"), self)
        self.btnConfirmCrop.hide();  self.btnCancelCrop.hide()
        h_crop.addWidget(self.btnCrop)
        h_crop.addWidget(self.btnConfirmCrop)
        h_crop.addWidget(self.btnCancelCrop)
        layout.addLayout(h_crop)
        # 第二行：校正按鈕
        h_straight = QHBoxLayout()
        self.btnStraight = QPushButton(tr("校正"), self)
        self.btnConfirm  = QPushButton(tr("確認校正"), self)
        self.btnCancel   = QPushButton(tr("取消校正"), self)
        self.btnConfirm.hide();  self.btnCancel.hide()
        h_straight.addWidget(self.btnStraight)
        h_straight.addWidget(self.btnConfirm)
        h_straight.addWidget(self.btnCancel)
        layout.addLayout(h_straight)
        # 連接信號
        self.btnCrop.clicked.connect(self.onCrop)
        self.btnConfirmCrop.clicked.connect(lambda: self.window().confirmCrop())
        self.btnCancelCrop.clicked.connect(lambda: self.window().cancelCrop())
        self.btnStraight.clicked.connect(self.onStraight)
        self.btnConfirm.clicked.connect(lambda: self.window().confirmStraighten())
        self.btnCancel.clicked.connect(lambda: self.window().cancelStraighten())
        # 調整面板高度以置入兩行按鈕
        layout.addStretch()
        self.setMaximumHeight(120)
        
    def onStraight(self):
        self.window().startStraightenMode()
    def onCrop(self):
        self.window().startCropMode()


class PreviewPanel(QDockWidget):
    def __init__(self, main_window):
        super().__init__(tr("切片預覽"), main_window)
        self.main = main_window
        self.setObjectName("previewPanel")
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # 預覽圖
        self.previewLabel = QLabel(self)
        self.previewLabel.setAlignment(Qt.AlignCenter)
        self.previewLabel.setObjectName("previewCanvas")
        layout.addWidget(self.previewLabel, alignment=Qt.AlignHCenter | Qt.AlignTop)

        # 名稱輸入框
        self.nameEdit = QLineEdit(self)
        self.nameEdit.setFont(theme_manager.ui_font(25))
        self.nameEdit.setAlignment(Qt.AlignCenter)
        self.nameEdit.setPlaceholderText(tr("切片名稱"))
        self.nameEdit.setFixedHeight(50)  # 控制高度
        layout.addWidget(self.nameEdit, alignment=Qt.AlignTop)
        layout.setSpacing(4)  # 再次確保間距較小

        # 上下切片按鈕區
        btnNavLayout = QHBoxLayout()
        btnNavLayout.setSpacing(4)
        self.btnPrev = QPushButton(tr("上一切片"), self)
        self.btnNext = QPushButton(tr("下一切片"), self)
        btnNavLayout.addWidget(self.btnPrev)
        btnNavLayout.addWidget(self.btnNext)
        layout.addLayout(btnNavLayout)

        # 切片資訊
        self.infoLabel = QLabel(self)
        self.infoLabel.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.infoLabel)

        # 預計導出名
        self.exportNameLabel = QLabel(self)
        self.exportNameLabel.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.exportNameLabel)
        layout.addStretch(1)  # 讓內容靠上，剩餘空間在下方

        # 尚未載入圖片時顯示的引導提示。
        self.emptyHint = QLabel(
            tr("尚未打開圖片\n\n拖入圖片、文件夾\n或按 Ctrl+O 導入"),
            self,
        )
        self.emptyHint.setObjectName("previewEmptyHint")
        self.emptyHint.setAlignment(Qt.AlignCenter)
        self.emptyHint.setWordWrap(True)
        layout.addWidget(self.emptyHint)
        layout.addStretch(1)

        widget.setLayout(layout)
        self.setWidget(widget)

        # 綁定事件
        self.nameEdit.returnPressed.connect(self.goto_next_slice)
        self.nameEdit.installEventFilter(self)
        self.nameEdit.textEdited.connect(self.apply_name)
        self.btnPrev.clicked.connect(self.goto_prev_slice)
        self.btnNext.clicked.connect(self.goto_next_slice)

    def eventFilter(self, obj, event):
        # 僅當焦點在 nameEdit 輸入框時才響應快捷鍵
        if obj == self.nameEdit and event.type() == event.KeyPress:
            if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Left:
                self.main.prevImage()
                return True
            elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Right:
                self.main.nextImage()
                return True
            elif self.nameEdit.hasFocus():
                if event.key() == Qt.Key_Up:
                    self.goto_prev_slice()
                    return True
                elif event.key() == Qt.Key_Down:
                    self.goto_next_slice()
                    return True
        return super().eventFilter(obj, event)

    def set_slice_list(self, slice_list):
        self.slice_list = slice_list

    def update_preview(self, slice_item):
        # 預覽圖與面板可見性控制
        # 若尚未載入圖片，清空並隱藏所有預覽相關控件
        if not getattr(self.main.sliceView, "image_item", None):
            self.previewLabel.clear()
            self.previewLabel.setVisible(False)
            self.emptyHint.setVisible(True)
            self.nameEdit.setVisible(False)
            # 若隱藏了輸入框，移除其焦點並把焦點返回主視窗，
            # 以便全局/窗口級的快捷鍵（如 Ctrl+Left / Ctrl+Right）仍可觸發
            try:
                self.nameEdit.clearFocus()
                self.main.setFocus()
            except Exception:
                pass
            self.btnPrev.setVisible(False)
            self.btnNext.setVisible(False)
            self.exportNameLabel.setVisible(False)
            self.infoLabel.setText("")
            return

        # 取得當前圖片資訊
        pixmap = self.main.sliceView.image_item.pixmap()
        img_w, img_h = pixmap.width(), pixmap.height()
        img_path = getattr(self.main, "currentImagePath", None)
        img_name = os.path.basename(img_path) if img_path else tr("(未命名圖片)")

        # 當有圖片但未選中任何切片：隱藏預覽框、名稱與導航按鈕，顯示檔名與尺寸（換行）
        if not slice_item:
            self.previewLabel.clear()
            self.previewLabel.setVisible(False)
            self.emptyHint.setVisible(False)
            self.nameEdit.setVisible(False)
            # 同上：當頁面沒有切片時，輸入框會被隱藏，應把焦點移回主視窗，
            # 否則使用者無法再用快捷鍵繼續翻頁
            try:
                self.nameEdit.clearFocus()
                self.main.setFocus()
            except Exception:
                pass
            self.btnPrev.setVisible(False)
            self.btnNext.setVisible(False)
            self.exportNameLabel.setVisible(False)
            self.infoLabel.setText(tr('當前圖片：{0}\n圖片尺寸：{1} 像素 x {2} 像素\n切片總數：{3}').format(img_name, img_w, img_h, self.slice_list.count() if hasattr(self, 'slice_list') else 0))
            return

        # 若有選中切片，恢復顯示預覽相關控件並填充資訊
        self.emptyHint.setVisible(False)
        rect = slice_item.rect().toRect()
        cropped = pixmap.copy(rect)
        preview = cropped.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.previewLabel.setPixmap(preview)
        self.previewLabel.setVisible(True)
        # 名稱
        self.nameEdit.blockSignals(True)
        self.nameEdit.setText(slice_item.name)
        self.nameEdit.blockSignals(False)
        self.nameEdit.setVisible(True)
        # 顯示上一/下一切片按鈕
        self.btnPrev.setVisible(True)
        self.btnNext.setVisible(True)
        # 切片資訊
        info = tr('切片 {0}（X:{1}  Y:{2}  寬:{3}  高:{4}）').format(slice_item.number, int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))
        self.infoLabel.setText(info)
        # 預計導出名
        base = getattr(self.main, "originalBaseName", "IMAGE")
        idx = slice_item.number
        name = slice_item.name.strip()
        fmt = self.main.defaultExportFormat if getattr(self.main, "defaultExportFormat", "") else ""
        if name:
            filename = f"{base}_{idx:03d}_{name}"
        else:
            filename = f"{base}_{idx:03d}"
        if fmt:
            filename = f"{filename}.{fmt.lower()}"
        self.exportNameLabel.setText(tr('預計導出名：{0}').format(filename))
        self.exportNameLabel.setVisible(True)

    def apply_name(self):
        # 將輸入框內容寫回切片
        if not hasattr(self, "slice_list"):
            return
        items = self.slice_list.selectedItems()
        if items:
            slice_item = items[0].data(Qt.UserRole)
            if slice_item:
                old_name = slice_item.name
                new_name = self.nameEdit.text()
                slice_item.name = new_name
                # 只更新對應的列表項文字，避免每次輸入都重建整個列表（會造成焦點/IME 被打斷）
                try:
                    # 在 slice_list 中尋找與 slice_item 關聯的 QListWidgetItem 並更新其標題
                    for i in range(self.slice_list.count()):
                        lw_item = self.slice_list.item(i)
                        if lw_item.data(Qt.UserRole) is slice_item:
                            rect = slice_item.rect()
                            x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
                            if new_name:
                                text = tr('切片 {0} | {1}（{2},{3} | {4}x{5}）').format(slice_item.number, new_name, x, y, w, h)
                            else:
                                text = tr('切片 {0}（{1},{2} | {3}x{4}）').format(slice_item.number, x, y, w, h)
                            lw_item.setText(text)
                            break
                except Exception:
                    # 回退：若發生任何錯誤，再嘗試一次完整刷新（較罕見）
                    try:
                        self.main.updateSliceList()
                    except Exception:
                        pass
                # 更新預覽（包含導出檔名等顯示）
                self.update_preview(slice_item)
                if old_name != new_name and hasattr(self.main, "markProjectEdited"):
                    self.main.markProjectEdited()

    def goto_next_slice(self):
        self.apply_name()
        if not hasattr(self, "slice_list"):
            return
        items = self.slice_list.selectedItems()
        if not items:
            if self.slice_list.count() > 0:
                # 選中第一個切片
                self.slice_list.setCurrentRow(0)
                self.slice_list.item(0).setSelected(True)
                self.slice_list.scrollToItem(self.slice_list.item(0))
                # 視圖置中第一個切片
                first = self.slice_list.item(0).data(Qt.UserRole)
                self.main.sliceView.centerOn(first)
                self.nameEdit.setFocus()
                self.nameEdit.selectAll()
                self.main.statusBar().showMessage(tr("已自動選擇第一張切片"))
            return
        current_slice = items[0].data(Qt.UserRole)
        current_number = current_slice.number
        target_row = None
        for i in range(self.slice_list.count()):
            slice_item = self.slice_list.item(i).data(Qt.UserRole)
            if slice_item and slice_item.number == current_number + 1:
                target_row = i
                break
        if target_row is not None:
            self.slice_list.clearSelection()
            self.slice_list.setCurrentRow(target_row)
            self.slice_list.item(target_row).setSelected(True)
            self.slice_list.scrollToItem(self.slice_list.item(target_row))
            # 視圖置中新選中的切片
            new_slice = self.slice_list.item(target_row).data(Qt.UserRole)
            self.main.sliceView.centerOn(new_slice)
            self.nameEdit.setFocus()
            self.nameEdit.selectAll()
        else:
            QApplication.beep()
            self.main.statusBar().showMessage(tr("已是最後一張切片"))

    def goto_prev_slice(self):
        self.apply_name()
        if not hasattr(self, "slice_list"):
            return
        items = self.slice_list.selectedItems()
        if not items:
            if self.slice_list.count() > 0:
                self.slice_list.setCurrentRow(0)
                self.slice_list.item(0).setSelected(True)
                self.slice_list.scrollToItem(self.slice_list.item(0))
                # 視圖置中第一個切片
                first = self.slice_list.item(0).data(Qt.UserRole)
                self.main.sliceView.centerOn(first)
                self.nameEdit.setFocus()
                self.nameEdit.selectAll()
                self.main.statusBar().showMessage(tr("已自動選擇第一張切片"))
            return
        current_slice = items[0].data(Qt.UserRole)
        current_number = current_slice.number
        target_row = None
        for i in range(self.slice_list.count()):
            slice_item = self.slice_list.item(i).data(Qt.UserRole)
            if slice_item and slice_item.number == current_number - 1:
                target_row = i
                break
        if target_row is not None:
            self.slice_list.clearSelection()
            self.slice_list.setCurrentRow(target_row)
            self.slice_list.item(target_row).setSelected(True)
            self.slice_list.scrollToItem(self.slice_list.item(target_row))
            # 視圖置中新選中的切片
            new_slice = self.slice_list.item(target_row).data(Qt.UserRole)
            self.main.sliceView.centerOn(new_slice)
            self.nameEdit.setFocus()
            self.nameEdit.selectAll()
        else:
            QApplication.beep()
            self.main.statusBar().showMessage(tr("已是第一張切片"))


class AutoProcessPanel(QDockWidget):
    def __init__(self, parent=None):
        super().__init__(tr("自動處理"), parent)
        self.main = parent
        self.script_dir = Path.home() / "Documents" / "HulenCut Script"
        self.script_dir.mkdir(parents=True, exist_ok=True)

        self.btn_record = QPushButton(tr("錄製脚本"))
        self.btn_import = QPushButton(tr("導入脚本"))
        self.btn_open_folder = QPushButton(tr("脚本文件夾"))
        self.btn_delete = QPushButton(tr("刪除"))
        self.btn_run = QPushButton(tr("運行"))
        self.btn_loop = QPushButton(tr("跨頁循環"))
        self.btn_loop.setToolTip(tr("循環執行脚本，跨頁自動處理"))
        self.script_list = QListWidget()
        self.script_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.script_list.customContextMenuRequested.connect(self.show_context_menu)
        self.script_list.keyPressEvent = self._script_list_keyPressEvent

        layout = QVBoxLayout()
        btn_top = QHBoxLayout()
        btn_top.addWidget(self.btn_record)
        btn_top.addWidget(self.btn_import)
        layout.addLayout(btn_top)
        btn_middle = QHBoxLayout()
        btn_middle.addWidget(self.btn_open_folder)
        btn_middle.addWidget(self.btn_delete)
        layout.addLayout(btn_middle)
        layout.addWidget(self.script_list)
        btn_bottom = QHBoxLayout()
        btn_bottom.addWidget(self.btn_run)
        btn_bottom.addWidget(self.btn_loop)  # 新增跨頁循環
        layout.addLayout(btn_bottom)

        widget = QWidget()
        widget.setLayout(layout)
        self.setWidget(widget)

        # 連接「脚本文件夾」按鈕
        self.btn_open_folder.clicked.connect(self.open_script_folder)
        # 跨頁循環按鈕事件
        self.btn_loop.clicked.connect(self.loop_script)
        # 根據導入模式更新按鈕狀態
        self.update_loop_button_state()

    def update_loop_button_state(self):
        # 僅在導入文件夾模式下可用
        if hasattr(self.main, "folderImages") and self.main.folderImages and len(self.main.folderImages) > 1:
            self.btn_loop.setEnabled(True)
        else:
            self.btn_loop.setEnabled(False)

    def show_context_menu(self, pos):
        menu = QMenu()
        rename_action = menu.addAction(tr("重命名"))
        delete_action = menu.addAction(tr("刪除"))
        item = self.script_list.itemAt(pos)
        if not item: return
        action = menu.exec_(self.script_list.mapToGlobal(pos))
        if action == rename_action:
            new_name, ok = QInputDialog.getText(self, tr("重命名脚本"), tr("新名稱:"), text=item.text())
            if ok and new_name:
                old_path = self.script_dir / f"{item.text()}.cscript"
                new_path = self.script_dir / f"{new_name}.cscript"
                if not new_path.exists():
                    old_path.rename(new_path)
                    item.setText(new_name)
        elif action == delete_action:
            (self.script_dir / f"{item.text()}.cscript").unlink()
            self.script_list.takeItem(self.script_list.row(item))

    def _script_list_keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            item = self.script_list.currentItem()
            if item:
                # 調用主視窗的刪除脚本方法
                if hasattr(self.main, "delete_script"):
                    self.main.delete_script()
        else:
            # 保持原有行為
            super(QListWidget, self.script_list).keyPressEvent(event)

    def loop_script(self):
        # 檢査是否為文件夾模式
        if not (hasattr(self.main, "folderImages") and self.main.folderImages and len(self.main.folderImages) > 1):
            return
        item = self.script_list.currentItem()
        if not item:
            QApplication.beep()
            self.main.statusBar().showMessage(tr("請先選擇脚本"))
            return
        path = self.script_dir / f"{item.text()}.cscript"
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            QApplication.beep()
            self.main.statusBar().showMessage(tr('脚本讀取失敗：{0}').format(e))
            return
        if not lines:
            QApplication.beep()
            self.main.statusBar().showMessage(tr("脚本內容為空"))
            return
        last_cmd = lines[-1]
        if last_cmd not in ("nextImage", "prevImage"):
            QApplication.beep()
            self.main.statusBar().showMessage(tr("當前脚本不支持跨頁循環，請確保脚本最後動作爲上/下一張"))
            return
        direction = "next" if last_cmd == "nextImage" else "prev"
        
        # 顯示中止對話框
        dlg = QDialog(self.main)
        dlg.setWindowTitle(tr("跨頁循環"))
        dlg.setWindowModality(Qt.NonModal)
        vbox = QVBoxLayout(dlg)
        vbox.addWidget(QLabel(tr("正在跨頁批量自動處理……"), dlg))
        btn_abort = QPushButton(tr("中止"), dlg)
        vbox.addWidget(btn_abort)
        dlg.abort = False
        btn_abort.clicked.connect(lambda: setattr(dlg, 'abort', True))
        dlg.show()
        # 立刻讓對話框與主窗口可交互
        QApplication.processEvents()

        # 進入跨頁循環模式
        self.main.inLoopMode = True

        # 暫停所有 beeps
        old_beep = QApplication.beep
        QApplication.beep = lambda: None
        
        # 暫停列表 & 預覽更新
        old_usl = self.main.updateSliceList
        old_upp = self.main.update_preview_panel
        self.main.updateSliceList = lambda: None
        self.main.update_preview_panel = lambda: None
        
        while True:
            # 保持 UI 事件流暢，讓對話框可拖動
            QApplication.processEvents()
            cur_idx = self.main.currentImageIndex
            for cmd in lines:
                self.main.execute_command(cmd)
                # 每執行一條命令後允許 UI 事件處理
                QApplication.processEvents()
            # 點擊中止後，等執行完當前脚本（含最後翻頁命令）再退出
            if dlg.abort:
                break
            # 若最後一條命令執行後圖片索引未變則中止循環
            if self.main.currentImageIndex == cur_idx:
                break
                
        # 關閉中止對話框
        dlg.close()
        
        # 還原模式，最後再刷新一次停留頁面
        self.main.is_script_running = False
        self.main.inLoopMode = False

        # 恢復列表 & 預覽更新，並手動觸發一次
        self.main.updateSliceList = old_usl
        self.main.update_preview_panel = old_upp

        self.main.loadCurrentFolderImage()
        # 恢復 beep 並播放一次結束提示
        QApplication.beep = old_beep
        QApplication.beep()
        self.main.statusBar().showMessage(tr("脚本跨頁循環執行結束"))

    def open_script_folder(self):
        # 使用系統檔案管理器打開脚本存放目錄
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.script_dir)))


class AlignDistributeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        p = parent
        # 保存對應的 MainWindow 物件
        self.main = parent
        # 第一行
        h1 = QHBoxLayout()
        self.btnLeft     = QPushButton(tr("左對齊"));         h1.addWidget(self.btnLeft)
        self.btnHCenter  = QPushButton(tr("縱居中"));   h1.addWidget(self.btnHCenter)
        self.btnRight    = QPushButton(tr("右對齊"));         h1.addWidget(self.btnRight)
        self.btnVDistribute = QPushButton(tr("縱勻距"));    h1.addWidget(self.btnVDistribute)
        # 第二行
        h2 = QHBoxLayout()
        self.btnTop      = QPushButton(tr("頂對齊"));         h2.addWidget(self.btnTop)
        self.btnVCenter  = QPushButton(tr("橫居中"));   h2.addWidget(self.btnVCenter)
        self.btnBottom   = QPushButton(tr("底對齊"));         h2.addWidget(self.btnBottom)
        self.btnHDistribute = QPushButton(tr("橫勻距"));    h2.addWidget(self.btnHDistribute)
        # layout
        v = QVBoxLayout(self)
        v.addLayout(h1)
        v.addLayout(h2)
        self.setLayout(v)
        # 集中管理
        self.buttons = [
            self.btnLeft, self.btnHCenter, self.btnRight, self.btnVDistribute,
            self.btnTop, self.btnVCenter, self.btnBottom, self.btnHDistribute
        ]
        # 連接信號
        self.btnLeft.clicked.connect(p.align_left)
        self.btnHCenter.clicked.connect(p.align_hcenter)
        self.btnRight.clicked.connect(p.align_right)
        self.btnVDistribute.clicked.connect(p.distribute_vertical)
        self.btnTop.clicked.connect(p.align_top)
        self.btnVCenter.clicked.connect(p.align_vcenter)
        self.btnBottom.clicked.connect(p.align_bottom)
        self.btnHDistribute.clicked.connect(p.distribute_horizontal)

    def update_buttons_state(self):
        # 改用 self.main 獲取 sliceView
        sel = [
            it for it in self.main.sliceView.scene().selectedItems()
            if isinstance(it, SliceRect)
        ]
        enabled = len(sel) > 1
        for b in self.buttons:
            b.setEnabled(enabled)


class FindWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent  # MainWindow
        self.last_query = ""
        self.search_mode = "current"  # or 'folder'
        self.match_mode = "keyword"  # or 'exact'
        # folder search state
        self._folder_files = []
        self._folder_file_index = 0
        self._folder_line_index = 0
        self.setFixedHeight(110)

        # UI
        v = QVBoxLayout(self)
        # 第一行：僅輸入框（Prev/Next 按鈕已可控制搜尋）
        hl1 = QHBoxLayout()
        self.input = QLineEdit(self)
        self.input.setPlaceholderText(tr("輸入切片名稱"))
        hl1.addWidget(self.input)
        v.addLayout(hl1)

        # 第二行：向前搜索 / 向後搜索 按鈕
        hl2 = QHBoxLayout()
        self.btnPrev = QPushButton(tr("向前搜索"), self)
        self.btnNext = QPushButton(tr("向後搜索"), self)
        self.btnPrev.clicked.connect(self.on_prev_clicked)
        self.btnNext.clicked.connect(self.on_next_clicked)
        hl2.addWidget(self.btnPrev)
        hl2.addWidget(self.btnNext)
        v.addLayout(hl2)

        # 第三行：搜索範圍（下拉）與匹配模式（下拉）
        hl3 = QHBoxLayout()
        self.cboScope = QComboBox(self)
        self.cboScope.addItems([tr("當前圖片"), tr("當前文件夾")])
        # 0 -> current, 1 -> folder
        self.cboScope.setCurrentIndex(0)
        self.cboScope.currentIndexChanged.connect(lambda idx: self._on_search_mode_changed(idx))

        self.cboMatchMode = QComboBox(self)
        self.cboMatchMode.addItems([tr("關鍵字"), tr("全稱")])
        # 0 -> keyword, 1 -> exact
        self.cboMatchMode.setCurrentIndex(0)
        self.cboMatchMode.currentIndexChanged.connect(lambda idx: self._on_match_mode_changed(idx))

        hl3.addWidget(QLabel(tr("搜索範圍："), self))
        hl3.addWidget(self.cboScope)
        hl3.addSpacing(8)
        hl3.addWidget(QLabel(tr("匹配模式："), self))
        hl3.addWidget(self.cboMatchMode)
        v.addLayout(hl3)

        # 允許按 Enter 觸發搜索（預設為下一個匹配）
        self.input.returnPressed.connect(self.on_next_clicked)

    def _on_search_mode_changed(self, idx=None):
        # cboScope: 0 -> 當前圖片, 1 -> 文件夾
        try:
            self.search_mode = 'folder' if (self.cboScope.currentIndex() == 1) else 'current'
        except Exception:
            # 保持原有設定
            pass

    def _on_match_mode_changed(self, idx=None):
        # cboMatchMode: 0 -> 關鍵字, 1 -> 全稱
        try:
            self.match_mode = 'exact' if (self.cboMatchMode.currentIndex() == 1) else 'keyword'
        except Exception:
            pass

    def on_next_clicked(self):
        query = (self.input.text() or "").strip()
        if not query:
            if hasattr(self.main, 'statusBar'):
                self.main.statusBar().showMessage(tr("請輸入搜索內容"))
            QApplication.beep()
            return
        # 若 query 改變，重置狀態
        if query != self.last_query:
            self.last_query = query
            self._match_indices = []
            self._match_ptr = 0
            self.reset_folder_state()

        if getattr(self, 'search_mode', 'current') == 'current':
            # 如果沒有已構造的當前匹配清單，則建立並跳到第一個
            if not hasattr(self, '_current_matches') or not self._current_matches:
                self._search_current_image(query)
            else:
                # 選中下一個
                try:
                    if not hasattr(self, '_curr_match_index'):
                        self._curr_match_index = 0
                    item = self._current_matches[self._curr_match_index % len(self._current_matches)]
                    self._select_slice_item(item)
                    self._curr_match_index = (self._curr_match_index + 1) % len(self._current_matches)
                except Exception:
                    # fallback: 觸發完整搜索
                    self._search_current_image(query)
        else:
            # 文件夾模式：在 folder 中尋找下一個匹配
            self._search_folder(query, direction='next')

    def on_prev_clicked(self):
        query = (self.input.text() or "").strip()
        if not query:
            if hasattr(self.main, 'statusBar'):
                self.main.statusBar().showMessage(tr("請輸入搜索內容"))
            QApplication.beep()
            return
        if getattr(self, 'search_mode', 'current') == 'current':
            # 向後一個：減小指標並選中
            try:
                if not hasattr(self, '_current_matches') or not self._current_matches:
                    # 建立匹配清單但不自動移動到下一個，直接建立並指向最後一個
                    matches = []
                    for i in range(self.main.sliceList.count()):
                        item = self.main.sliceList.item(i)
                        s = item.data(Qt.UserRole)
                        name = getattr(s, 'name', '') or ''
                        if self._matches(name, query):
                            matches.append(item)
                    if not matches:
                        self.main.statusBar().showMessage(tr("當前圖片中未找到匹配的切片"))
                        return
                    self._current_matches = matches
                    self._curr_match_index = len(matches) - 1
                    item = self._current_matches[self._curr_match_index]
                    self._select_slice_item(item)
                else:
                    # 指標回退一位
                    try:
                        # 將 index 指向上一個（注意循環）
                        if not hasattr(self, '_curr_match_index'):
                            self._curr_match_index = 0
                        # 往前移動一位
                        self._curr_match_index = (self._curr_match_index - 1) % len(self._current_matches)
                        item = self._current_matches[self._curr_match_index]
                        self._select_slice_item(item)
                    except Exception:
                        self._search_current_image(query)
            except Exception:
                # fallback
                self._search_current_image(query)
        else:
            # 文件夾模式：在 folder 中尋找上一個匹配
            self._search_folder(query, direction='prev')

    def reset_folder_state(self):
        self._folder_files = []
        self._folder_file_index = 0
        self._folder_line_index = 0

    def on_search_clicked(self):
        query = (self.input.text() or "").strip()
        if not query:
            if hasattr(self.main, 'statusBar'):
                self.main.statusBar().showMessage(tr("請輸入搜索內容"))
                QApplication.beep()
            return

        # 若 query 或模式改變，重置狀態
        if query != self.last_query:
            self.last_query = query
            self._match_indices = []
            self._match_ptr = 0
            self.reset_folder_state()

        if self.search_mode == 'current':
            self._search_current_image(query)
        else:
            # folder mode: 在搜索前檢査是否需要保存當前工程
            ok = True
            try:
                ok = self.main.confirmDiscardSlices()
            except Exception:
                ok = True
            if not ok:
                # 使用者取消或保存失敗
                return
            self._search_folder(query)

    def _matches(self, name, query):
        # 防禦式處理：確保 name/query 都是字串並做 Unicode 正規化
        try:
            if name is None:
                return False
            n = unicodedata.normalize('NFKC', str(name)).strip()
            q = unicodedata.normalize('NFKC', str(query)).strip()
        except Exception:
            # 若正規化失敗，退回簡單比較
            try:
                if name is None:
                    return False
                n = str(name).strip()
                q = str(query).strip()
            except Exception:
                return False

        if self.match_mode == 'exact':
            # 全稱匹配：大小寫不敏感
            return n.lower() == q.lower()
        else:
            # 關鍵字匹配：大小寫不敏感，子串檢査
            return q.lower() in n.lower()

    def _select_slice_item(self, list_item):
        # 清除並選中目標切片，並在視圖中定位
        try:
            # 不阻塞 signals，讓列表與視圖的同步機制生效（以便顯示藍色選中與預覽）
            for i in range(self.main.sliceList.count()):
                it = self.main.sliceList.item(i)
                it.setSelected(False)
            list_item.setSelected(True)
            s = list_item.data(Qt.UserRole)
            if s:
                # 設置視圖選中並居中顯示
                try:
                    s.setSelected(True)
                except Exception:
                    pass
                self.main.sliceView.centerOn(s)
                # 也滾動列表到該項
                self.main.sliceList.scrollToItem(list_item)
                # 更新預覽與狀態欄
                try:
                    self.main.update_preview_panel()
                except Exception:
                    pass
                # 顯示當前圖片檔名（僅檔名含副檔名），若無則使用空字串
                img_path = getattr(self.main, 'currentImagePath', '') or ''
                img_name = os.path.basename(img_path) if img_path else ''
                self.main.statusBar().showMessage(tr('跳轉到：{0} 切片{1} | {2}').format(img_name, s.number, s.name))
        except Exception:
            pass

    def _search_current_image(self, query):
        # 收集匹配項目（基於切片名稱），並支援上一/下一導航
        matches = []
        for i in range(self.main.sliceList.count()):
            item = self.main.sliceList.item(i)
            s = item.data(Qt.UserRole)
            name = getattr(s, 'name', '') or ''
            if self._matches(name, query):
                matches.append(item)
        if not matches:
            # 保留當前圖片未找到時的提示（與原行為一致）
            self.main.statusBar().showMessage(tr("當前圖片中未找到匹配的切片"))
            QApplication.beep()
            # 清空任何先前的匹配狀態
            self._current_matches = []
            self._curr_match_index = 0
            return
        # 記錄匹配清單以供上一/下一使用
        self._current_matches = matches
        if not hasattr(self, '_curr_match_index'):
            self._curr_match_index = 0
        # 選中當前索引指向的項目（默認為 0）
        try:
            item = self._current_matches[self._curr_match_index % len(self._current_matches)]
            self._select_slice_item(item)
            # 下一次移動到下一個
            self._curr_match_index = (self._curr_match_index + 1) % len(self._current_matches)
        except Exception:
            # 若有異常，重置並選中第一個
            self._curr_match_index = 0
            item = self._current_matches[0]
            self._select_slice_item(item)

    def _search_folder(self, query, direction='next', allow_prompt=True, restart=False):
        # 構造 .cutter 檔列表（若尚未構造）
        if not self._folder_files:
            directory = None
            if getattr(self.main, 'currentFolder', None):
                directory = self.main.currentFolder
            elif getattr(self.main, 'currentImagePath', None):
                directory = os.path.dirname(self.main.currentImagePath)
            if not directory:
                self.main.statusBar().showMessage(tr("沒有可搜索的文件夾"))
                return
            files = [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith('.cutter')]
            files.sort()
            self._folder_files = files

        files = self._folder_files
        # 為每個文件構造匹配索引（如果尚未構造或 query 不同）
        rebuild = (not hasattr(self, '_folder_matches')) or (getattr(self, '_folder_matches_query', None) != query)
        if rebuild:
            self._folder_matches = []
            for fp in files:
                try:
                    with open(fp, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                except Exception:
                    lines = []
                matches_idx = []
                for idx, ln in enumerate(lines):
                    parts = ln.strip().split('\t')
                    name = parts[4] if len(parts) >= 5 else ''
                    if self._matches(name, query):
                        matches_idx.append(idx)
                self._folder_matches.append(matches_idx)
            self._folder_matches_query = query

        # 判定當前頁碼 (file index)
        cur_file_idx = 0
        # 若要求從頭/尾重試，則直接指定起始檔案索引
        if restart:
            if direction == 'next':
                cur_file_idx = -1  # 之後的 range(cur_file_idx+1, ...) 會從 0 開始
            else:
                cur_file_idx = len(files)  # 之後向前搜尋時會從 len(files)-1 開始
        else:
            try:
                cur_img = getattr(self.main, 'currentImagePath', None)
                if cur_img:
                    cur_base = os.path.splitext(os.path.basename(cur_img))[0]
                    # 嘗試找到與當前圖片對應的 .cutter 文件（同名 .cutter）
                    for i, fp in enumerate(files):
                        if os.path.splitext(os.path.basename(fp))[0] == cur_base:
                            cur_file_idx = i
                            break
                elif hasattr(self.main, 'currentImageIndex') and getattr(self.main, 'folderImages', None):
                    # 若有 folderImages 並且 currentImageIndex 可用，尋找與該圖片同名的 .cutter
                    try:
                        img = self.main.folderImages[self.main.currentImageIndex]
                        img_base = os.path.splitext(os.path.basename(img))[0]
                        for i, fp in enumerate(files):
                            if os.path.splitext(os.path.basename(fp))[0] == img_base:
                                cur_file_idx = i
                                break
                    except Exception:
                        pass
            except Exception:
                # 如果重試模式或發生錯誤，保持 cur_file_idx 的預設值
                pass

        # 判定當前選中切片的 index（list index, 0-based）
        cur_slice_index = -1
        try:
            sel = [self.main.sliceList.item(i) for i in range(self.main.sliceList.count()) if self.main.sliceList.item(i).isSelected()]
            if sel:
                # 找到第一個被選中的項目，取得其索引
                selected_item = sel[0]
                for i in range(self.main.sliceList.count()):
                    if self.main.sliceList.item(i) == selected_item:
                        cur_slice_index = i
                        break
            else:
                # 如果沒有選中，對於 next 設為 -1（從頭開始），對於 prev 設為 len(list)（從尾開始）
                if direction == 'next':
                    cur_slice_index = -1
                else:
                    cur_slice_index = self.main.sliceList.count()
        except Exception:
            cur_slice_index = -1 if direction == 'next' else self.main.sliceList.count()

        found = False
        found_fp = None
        found_line = None

        if direction == 'next':
            # 先在當前頁面尋找 index > cur_slice_index
            matches_here = self._folder_matches[cur_file_idx] if 0 <= cur_file_idx < len(self._folder_matches) else []
            for m in matches_here:
                if m > cur_slice_index:
                    found = True
                    found_fp = files[cur_file_idx]
                    found_line = m
                    break
            # 向後頁面尋找第一個匹配
            if not found:
                for fi in range(cur_file_idx + 1, len(files)):
                    if self._folder_matches[fi]:
                        found = True
                        found_fp = files[fi]
                        found_line = self._folder_matches[fi][0]
                        break

        else:  # prev
            # 先在當前頁面尋找 index < cur_slice_index（取最大的那個）
            matches_here = self._folder_matches[cur_file_idx] if 0 <= cur_file_idx < len(self._folder_matches) else []
            prev_candidate = None
            for m in matches_here:
                if m < cur_slice_index:
                    prev_candidate = m
            if prev_candidate is not None:
                found = True
                found_fp = files[cur_file_idx]
                found_line = prev_candidate
            # 向前頁面尋找最後一個匹配
            if not found:
                for fi in range(cur_file_idx - 1, -1, -1):
                    if self._folder_matches[fi]:
                        found = True
                        found_fp = files[fi]
                        found_line = self._folder_matches[fi][-1]
                        break

        if found:
            # 打開該 .cutter 並選中對應行（與原來的載入流程保持一致）
            fp = found_fp
            idx = found_line
            try:
                # 嘗試定位對應的圖片並載入
                img_base = os.path.splitext(fp)[0]
                found_img = None
                for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp']:
                    cand = img_base + ext
                    if os.path.exists(cand):
                        found_img = cand
                        break
                if found_img:
                    try:
                        if not (hasattr(self.main, 'folderImages') and self.main.folderImages):
                            folder = os.path.dirname(found_img)
                            imgs = sorted([
                                os.path.join(folder, f)
                                for f in os.listdir(folder)
                                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp'))
                            ])
                            self.main.folderImages = imgs
                        try:
                            idx_img = self.main.folderImages.index(found_img)
                        except Exception:
                            idx_img = None
                        if idx_img is not None:
                            self.main.currentImageIndex = idx_img
                            self.main.loadCurrentFolderImage()
                        else:
                            self.main._suppressPreviewUpdate = True
                            self.main.sliceList.clear()
                            self.main.sliceView.loadImage(found_img)
                            self.main.currentImagePath = found_img
                            self.main._suppressPreviewUpdate = False
                            self.main.statusBar().showMessage(tr('載入圖片：{0}').format(os.path.basename(found_img)))
                    except Exception:
                        pass
                    try:
                        self.main.loadProjectFile(fp, tr('載入工程並跳轉：{0}').format(os.path.basename(fp)))
                    except Exception:
                        pass
                else:
                    self.main.loadProjectFile(fp, tr('載入工程並跳轉：{0}').format(os.path.basename(fp)))

                # 載入後選中對應行（若該行存在且匹配）
                try:
                    count = self.main.sliceList.count()
                    if idx < count:
                        it = self.main.sliceList.item(idx)
                        s = it.data(Qt.UserRole)
                        if getattr(s, 'name', '') and self._matches(s.name, query):
                            self._select_slice_item(it)
                        else:
                            # 異常情況時選中檔案中第一個匹配項
                            for i in range(count):
                                it2 = self.main.sliceList.item(i)
                                s2 = it2.data(Qt.UserRole)
                                if getattr(s2, 'name', '') and self._matches(s2.name, query):
                                    self._select_slice_item(it2)
                                    break
                    else:
                        for i in range(self.main.sliceList.count()):
                            it2 = self.main.sliceList.item(i)
                            s2 = it2.data(Qt.UserRole)
                            if getattr(s2, 'name', '') and self._matches(s2.name, query):
                                self._select_slice_item(it2)
                                break
                except Exception:
                    for i in range(self.main.sliceList.count()):
                        it = self.main.sliceList.item(i)
                        s = it.data(Qt.UserRole)
                        if getattr(s, 'name', '') and self._matches(s.name, query):
                            self._select_slice_item(it)
                            break
                # 更新 folder 狀態定位到當前檔案與下一行（保持兼容性）
                try:
                    self._folder_file_index = files.index(fp)
                    self._folder_line_index = idx + 1
                except Exception:
                    self._folder_file_index = 0
                    self._folder_line_index = 0
                return True
            except Exception as e:
                self.main.statusBar().showMessage(tr('載入工程失敗：{0}').format(e))
                return

        # 沒有找到匹配項
        try:
            QApplication.beep()
            if not allow_prompt:
                # 已禁用彈窗，直接返回未找到
                self.main.statusBar().showMessage(tr("在文件夾中沒有匹配項"))
                return False
            if direction == 'next':
                resp = QMessageBox.question(self.main, tr("搜尋結束"), tr("在文件夾中沒有更多匹配項。要從頭搜索嗎？"), QMessageBox.Yes | QMessageBox.No)
                if resp == QMessageBox.Yes:
                    # 從頭開始搜索一次（禁用再次彈窗以避免循環）
                    self._folder_matches_query = None
                    found_again = self._search_folder(query, direction='next', allow_prompt=False, restart=True)
                    if not found_again:
                        self.main.statusBar().showMessage(tr("在文件夾中沒有匹配項"))
                        QApplication.beep()
                    return found_again
                else:
                    self.main.statusBar().showMessage(tr("在文件夾中沒有匹配項"))
                    QApplication.beep()
                    return False
            else:
                resp = QMessageBox.question(self.main, tr("搜尋結束"), tr("在文件夾中沒有更早的匹配項。要從尾部搜索嗎？"), QMessageBox.Yes | QMessageBox.No)
                if resp == QMessageBox.Yes:
                    # 從尾開始反向搜索一次（禁用再次彈窗以避免循環）
                    self._folder_matches_query = None
                    found_again = self._search_folder(query, direction='prev', allow_prompt=False, restart=True)
                    if not found_again:
                        self.main.statusBar().showMessage(tr("在文件夾中沒有匹配項"))
                    return found_again
                else:
                    self.main.statusBar().showMessage(tr("在文件夾中沒有匹配項"))
                    return False
        except Exception:
            # 當對話框失敗時，仍顯示狀態欄提示
            self.main.statusBar().showMessage(tr("在文件夾中沒有匹配項"))
            return False
