"""Application dialogs."""
import re
import urllib.request

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QRadioButton, QSpinBox, QTextEdit, QVBoxLayout

from .i18n import tr


def _version_key(version: str) -> tuple[int, ...]:
    """Normalize version text and return a comparable numeric tuple."""
    text = str(version).replace("\ufeff", "").strip().lower()
    if text.startswith("v"):
        text = text[1:]
    numbers = re.findall(r"\d+", text)
    return tuple(int(part) for part in numbers)


def is_newer_version(current_version: str, latest_version: str) -> bool:
    current_key = _version_key(current_version)
    latest_key = _version_key(latest_version)
    if current_key and latest_key:
        return latest_key > current_key
    current_text = str(current_version).replace("\ufeff", "").strip().lower()
    latest_text = str(latest_version).replace("\ufeff", "").strip().lower()
    return latest_text != current_text


class DivideSlicesDialog(QDialog):
    last_params = {"cols": 2, "rows": 2, "method": "corner"}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("劃分切片"))
        layout = QFormLayout(self)
        description = QLabel(tr("・依指定的表格行列創建多個切片。"), self)
        description.setObjectName("hintLabel")
        layout.addRow(description)
        self.spinCols = QSpinBox(self)
        self.spinCols.setMinimum(1)  # 防止為0
        self.spinCols.setValue(DivideSlicesDialog.last_params["cols"])
        self.spinRows = QSpinBox(self)
        self.spinRows.setMinimum(1)  # 防止為0
        self.spinRows.setValue(DivideSlicesDialog.last_params["rows"])
        layout.addRow(tr("每橫行切片數量："), self.spinCols)
        layout.addRow(tr("每縱列切片數量："), self.spinRows)
        self.radioCorner = QRadioButton(tr("對角點"), self)
        self.radioCenter = QRadioButton(tr("對角切片中心點"), self)
        if DivideSlicesDialog.last_params["method"] == "center":
            self.radioCenter.setChecked(True)
        else:
            self.radioCorner.setChecked(True)
        radioLayout = QHBoxLayout()
        radioLayout.addWidget(self.radioCorner)
        radioLayout.addWidget(self.radioCenter)
        layout.addRow(tr("定位方式："), radioLayout)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)
        
    def getValues(self):
        cols = self.spinCols.value()
        rows = self.spinRows.value()
        method = "corner" if self.radioCorner.isChecked() else "center"
        # 保存參數以供下次使用
        DivideSlicesDialog.last_params = {
            "cols": cols, "rows": rows, "method": method
        }
        return cols, rows, method


class TableDetectDialog(QDialog):
    last_params = {"style": "白底黑字", "min_width": 40, "min_height": 40, "threshold": 0.5}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("自動識別表格"))
        layout = QFormLayout(self)
        
        # 圖片風格選擇
        self.styleGroup = QButtonGroup(self)
        self.radioWhite = QRadioButton(tr("白底黑字"), self)
        self.radioBlack = QRadioButton(tr("黑底白字"), self)
        # 使用上次的風格設定
        if TableDetectDialog.last_params["style"] == "黑底白字":
            self.radioBlack.setChecked(True)
        else:
            self.radioWhite.setChecked(True)
        self.styleGroup.addButton(self.radioWhite)
        self.styleGroup.addButton(self.radioBlack)
        styleLayout = QHBoxLayout()
        styleLayout.addWidget(self.radioWhite)
        styleLayout.addWidget(self.radioBlack)
        layout.addRow(tr("圖片風格："), styleLayout)
        
        # 最小寬度，使用上次的設定
        self.spinMinWidth = QSpinBox(self)
        self.spinMinWidth.setRange(1, 1000)
        self.spinMinWidth.setValue(TableDetectDialog.last_params["min_width"])
        self.spinMinWidth.setSuffix(" px")
        layout.addRow(tr("最小寬度："), self.spinMinWidth)
        
        # 最小高度，使用上次的設定
        self.spinMinHeight = QSpinBox(self)
        self.spinMinHeight.setRange(1, 1000)
        self.spinMinHeight.setValue(TableDetectDialog.last_params["min_height"])
        self.spinMinHeight.setSuffix(" px")
        layout.addRow(tr("最小高度："), self.spinMinHeight)
        
        # 檢測閾值，使用上次的設定
        self.spinThreshold = QDoubleSpinBox(self)
        self.spinThreshold.setRange(0.01, 1.0)
        self.spinThreshold.setValue(TableDetectDialog.last_params["threshold"])
        self.spinThreshold.setSingleStep(0.05)
        layout.addRow(tr("檢測閾值："), self.spinThreshold)
        
        # 按鈕
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)
    
    def getValues(self):
        style = "白底黑字" if self.radioWhite.isChecked() else "黑底白字"
        values = {
            "style": style,
            "min_width": self.spinMinWidth.value(),
            "min_height": self.spinMinHeight.value(),
            "threshold": self.spinThreshold.value()
        }
        # 保存參數以供下次使用
        TableDetectDialog.last_params = values.copy()
        return values


class NormalizeSlicesDialog(QDialog):
    last_params = {"range": "all", "width": 100, "height": 100, "enable_width": True, "enable_height": True}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("切片定幅"))
        layout = QFormLayout(self)
        description = QLabel(tr("・將特定切片統一爲指定的寬高。"), self)
        description.setObjectName("hintLabel")
        layout.addRow(description)
        # 目標範圍選項
        self.radioAll = QRadioButton(tr("全部"), self)
        self.radioSelected = QRadioButton(tr("已選擇"), self)
        self.radioAll.setChecked(True)
        radioLayout = QHBoxLayout()
        radioLayout.addWidget(self.radioAll)
        radioLayout.addWidget(self.radioSelected)
        layout.addRow(tr("切片範圍："), radioLayout)
        
        # 輸入指定寬高（帶勾選框）
        # 寬度設置
        widthLayout = QHBoxLayout()
        self.checkWidth = QCheckBox(self)
        self.checkWidth.setChecked(NormalizeSlicesDialog.last_params.get("enable_width", True))
        self.spinWidth = QSpinBox(self)
        self.spinWidth.setRange(1, 10000)
        self.spinWidth.setValue(NormalizeSlicesDialog.last_params.get("width", 100))
        self.spinWidth.setSuffix(" px")
        widthLayout.addWidget(self.checkWidth)
        widthLayout.addWidget(self.spinWidth)
        layout.addRow(tr("指定寬度："), widthLayout)
        
        # 高度設置
        heightLayout = QHBoxLayout()
        self.checkHeight = QCheckBox(self)
        self.checkHeight.setChecked(NormalizeSlicesDialog.last_params.get("enable_height", True))
        self.spinHeight = QSpinBox(self)
        self.spinHeight.setRange(1, 10000)
        self.spinHeight.setValue(NormalizeSlicesDialog.last_params.get("height", 100))
        self.spinHeight.setSuffix(" px")
        heightLayout.addWidget(self.checkHeight)
        heightLayout.addWidget(self.spinHeight)
        layout.addRow(tr("指定高度："), heightLayout)
        
        # 連接勾選框事件來更新控件狀態
        self.checkWidth.stateChanged.connect(self.updateWidthState)
        self.checkHeight.stateChanged.connect(self.updateHeightState)
        
        # 初始化狀態
        self.updateWidthState()
        self.updateHeightState()
        
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)
    
    def updateWidthState(self):
        """Update the enabled state of the width input."""
        enabled = self.checkWidth.isChecked()
        self.spinWidth.setEnabled(enabled)
    
    def updateHeightState(self):
        """Update the enabled state of the height input."""
        enabled = self.checkHeight.isChecked()
        self.spinHeight.setEnabled(enabled)
    
    def getValues(self):
        target = "all" if self.radioAll.isChecked() else "selected"
        enable_width = self.checkWidth.isChecked()
        enable_height = self.checkHeight.isChecked()
        width = self.spinWidth.value() if enable_width else None
        height = self.spinHeight.value() if enable_height else None
        
        # 保存參數以供下次使用
        NormalizeSlicesDialog.last_params = {
            "range": target,
            "width": self.spinWidth.value(),
            "height": self.spinHeight.value(),
            "enable_width": enable_width,
            "enable_height": enable_height
        }
        
        return target, width, height


class MoveSlicesDialog(QDialog):
    last_params = {"range": "all", "moveX": 0, "moveY": 0}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("移動切片"))
        layout = QFormLayout(self)
        description = QLabel(tr("・將特定切片批量位移。負數爲反向。"), self)
        description.setObjectName("hintLabel")
        layout.addRow(description)
        # 改成橫向排列
        self.radioAll = QRadioButton(tr("全部"), self)
        self.radioSelected = QRadioButton(tr("已選擇"), self)
        if MoveSlicesDialog.last_params["range"] == "selected":
            self.radioSelected.setChecked(True)
        else:
            self.radioAll.setChecked(True)
        radioLayout = QHBoxLayout()
        radioLayout.addWidget(self.radioAll)
        radioLayout.addWidget(self.radioSelected)
        layout.addRow(tr("切片範圍："), radioLayout)
        self.spinX = QSpinBox(self)
        self.spinX.setRange(-10000, 10000)
        self.spinX.setValue(0)
        self.spinX.setSuffix(" px")
        self.spinX.setValue(MoveSlicesDialog.last_params["moveX"])
        self.spinY = QSpinBox(self)
        self.spinY.setRange(-10000, 10000)
        self.spinY.setValue(0)
        self.spinY.setSuffix(" px")
        self.spinY.setValue(MoveSlicesDialog.last_params["moveY"])
        layout.addRow(tr("向右移動："), self.spinX)
        layout.addRow(tr("向下移動："), self.spinY)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)

    def getValues(self):
        target = "all" if self.radioAll.isChecked() else "selected"
        moveX = self.spinX.value()
        moveY = self.spinY.value()
        MoveSlicesDialog.last_params = {
            "range": target, "moveX": moveX, "moveY": moveY
        }
        return (target, moveX, moveY)


class ScaleSlicesDialog(QDialog):
    last_params = {"range": "all", "scaleX": 100.00, "scaleY": 100.00}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("縮放切片"))
        layout = QFormLayout(self)
        description = QLabel(tr("・將特定切片按比例從中心縮放。"), self)
        description.setObjectName("hintLabel")
        layout.addRow(description)
        # 改成橫向排列
        self.radioAll = QRadioButton(tr("全部"), self)
        self.radioSelected = QRadioButton(tr("已選擇"), self)
        if ScaleSlicesDialog.last_params["range"] == "selected":
            self.radioSelected.setChecked(True)
        else:
            self.radioAll.setChecked(True)
        radioLayout = QHBoxLayout()
        radioLayout.addWidget(self.radioAll)
        radioLayout.addWidget(self.radioSelected)
        layout.addRow(tr("切片範圍："), radioLayout)
        self.spinX = QDoubleSpinBox(self)
        self.spinX.setRange(0.01, 1000.00)
        self.spinX.setDecimals(2)
        self.spinX.setValue(100.00)
        self.spinX.setSuffix(" %")
        self.spinX.setValue(ScaleSlicesDialog.last_params["scaleX"])
        self.spinY = QDoubleSpinBox(self)
        self.spinY.setRange(0.01, 1000.00)
        self.spinY.setDecimals(2)
        self.spinY.setValue(100.00)
        self.spinY.setSuffix(" %")
        self.spinY.setValue(ScaleSlicesDialog.last_params["scaleY"])
        layout.addRow(tr("橫向比例："), self.spinX)
        layout.addRow(tr("縱向比例："), self.spinY)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)

    def getValues(self):
        target = "all" if self.radioAll.isChecked() else "selected"
        scaleX = self.spinX.value()
        scaleY = self.spinY.value()
        ScaleSlicesDialog.last_params = {
            "range": target, "scaleX": scaleX, "scaleY": scaleY
        }
        return (target, scaleX, scaleY)


class ScaleProjectDialog(QDialog):
    last_scale_factor = 1.0
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("縮放工程座標"))
        layout = QFormLayout(self)
        description = QLabel(tr("・用於統合圖幅不一的圖像與工程。"), self)
        description.setObjectName("hintLabel")
        layout.addRow(description)
        
        # 縮放係數輸入框
        self.spinScale = QDoubleSpinBox(self)
        self.spinScale.setRange(0.01, 1000.00)
        self.spinScale.setDecimals(2)
        self.spinScale.setSingleStep(0.5)  # 每次增減0.5
        self.spinScale.setValue(ScaleProjectDialog.last_scale_factor)
        layout.addRow(tr("縮放係數："), self.spinScale)
        
        # 按鈕
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)

    def getScaleFactor(self):
        scale_factor = self.spinScale.value()
        ScaleProjectDialog.last_scale_factor = scale_factor
        return scale_factor


class FilterSlicesDialog(QDialog):
    last_params = {
        "range": "all", 
        "condition1": {"dimension": "w", "operator": "greater", "value": 100},
        "logic": None,  # None, "or", "and"
        "condition2": {"dimension": "h", "operator": "greater", "value": 100}
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("篩除切片"))
        layout = QFormLayout(self)
        description = QLabel(tr("・刪除滿足特定寬高條件的切片。"), self)
        description.setObjectName("hintLabel")
        layout.addRow(description)
        
        # 第一行：切片範圍
        self.radioAll = QRadioButton(tr("全部"), self)
        self.radioSelected = QRadioButton(tr("已選擇"), self)
        if FilterSlicesDialog.last_params["range"] == "selected":
            self.radioSelected.setChecked(True)
        else:
            self.radioAll.setChecked(True)
        self.rangeGroup = QButtonGroup(self)
        self.rangeGroup.addButton(self.radioAll)
        self.rangeGroup.addButton(self.radioSelected)
        radioLayout = QHBoxLayout()
        radioLayout.addWidget(self.radioAll)
        radioLayout.addWidget(self.radioSelected)
        layout.addRow(tr("切片範圍："), radioLayout)
        
        # 第二行：第一個條件
        condition1Layout = QHBoxLayout()
        self.combo1Dimension = QComboBox(self)
        self.combo1Dimension.addItems([tr("寬"), tr("高")])
        self.combo1Dimension.setCurrentText(tr("寬") if FilterSlicesDialog.last_params["condition1"]["dimension"] == "w" else tr("高"))
        
        self.combo1Operator = QComboBox(self)
        self.combo1Operator.addItems([tr("大於"), tr("等於"), tr("小於")])
        op_map = {"greater": tr("大於"), "equal": tr("等於"), "less": tr("小於")}
        self.combo1Operator.setCurrentText(op_map.get(FilterSlicesDialog.last_params["condition1"]["operator"], tr("小於")))
        
        self.spin1Value = QSpinBox(self)
        self.spin1Value.setRange(1, 10000)
        self.spin1Value.setValue(FilterSlicesDialog.last_params["condition1"]["value"])
        self.spin1Value.setSuffix(" px")
        
        condition1Layout.addWidget(self.combo1Dimension)
        condition1Layout.addWidget(self.combo1Operator)
        condition1Layout.addWidget(self.spin1Value)
        layout.addRow(tr("條件一："), condition1Layout)
        
        # 第三行：邏輯連接詞
        logicLayout = QHBoxLayout()
        self.checkOr = QCheckBox(tr("或"), self)
        self.checkAnd = QCheckBox(tr("和"), self)
        
        # 設置初始狀態
        if FilterSlicesDialog.last_params["logic"] == "or":
            self.checkOr.setChecked(True)
        elif FilterSlicesDialog.last_params["logic"] == "and":
            self.checkAnd.setChecked(True)
        
        # 連接事件處理
        self.checkOr.stateChanged.connect(self.onLogicChanged)
        self.checkAnd.stateChanged.connect(self.onLogicChanged)
        
        logicLayout.addWidget(self.checkOr)
        logicLayout.addWidget(self.checkAnd)
        layout.addRow(tr("篩除邏輯："), logicLayout)
        
        # 第四行：第二個條件
        condition2Layout = QHBoxLayout()
        self.combo2Dimension = QComboBox(self)
        self.combo2Dimension.addItems([tr("寬"), tr("高")])
        self.combo2Dimension.setCurrentText(tr("高") if FilterSlicesDialog.last_params["condition2"]["dimension"] == "h" else tr("寬"))
        
        self.combo2Operator = QComboBox(self)
        self.combo2Operator.addItems([tr("大於"), tr("等於"), tr("小於")])
        self.combo2Operator.setCurrentText(op_map.get(FilterSlicesDialog.last_params["condition2"]["operator"], tr("大於")))
        
        self.spin2Value = QSpinBox(self)
        self.spin2Value.setRange(1, 10000)
        self.spin2Value.setValue(FilterSlicesDialog.last_params["condition2"]["value"])
        self.spin2Value.setSuffix(" px")
        
        condition2Layout.addWidget(self.combo2Dimension)
        condition2Layout.addWidget(self.combo2Operator)
        condition2Layout.addWidget(self.spin2Value)
        
        # 直接添加布局，不使用額外的容器
        layout.addRow(tr("條件二："), condition2Layout)
        
        # 設置第二行的初始啟用狀態
        self.updateCondition2State()
        
        # 按鈕
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        layout.addRow(self.buttonBox)
    
    def onLogicChanged(self):
        # 確保最多只能選擇一個邏輯操作符
        sender = self.sender()
        if sender == self.checkOr and self.checkOr.isChecked():
            self.checkAnd.setChecked(False)
        elif sender == self.checkAnd and self.checkAnd.isChecked():
            self.checkOr.setChecked(False)
        
        self.updateCondition2State()
    
    def updateCondition2State(self):
        # 當沒有選擇邏輯操作符時，禁用第二個條件的所有控件
        has_logic = self.checkOr.isChecked() or self.checkAnd.isChecked()
        self.combo2Dimension.setEnabled(has_logic)
        self.combo2Operator.setEnabled(has_logic)
        self.spin2Value.setEnabled(has_logic)
    
    def getValues(self):
        # 獲取範圍
        target = "all" if self.radioAll.isChecked() else "selected"
        
        # 獲取第一個條件
        dim1 = "w" if self.combo1Dimension.currentText() == tr("寬") else "h"
        op1_map = {tr("大於"): "greater", tr("等於"): "equal", tr("小於"): "less"}
        op1 = op1_map[self.combo1Operator.currentText()]
        val1 = self.spin1Value.value()
        condition1 = [dim1, op1, val1]
        
        # 獲取邏輯操作符
        logic = None
        if self.checkOr.isChecked():
            logic = "or"
        elif self.checkAnd.isChecked():
            logic = "and"
        
        # 獲取第二個條件（如果有邏輯操作符）
        condition2 = None
        dim2 = "h"  # 默認值
        op2 = "greater"  # 默認值
        val2 = 100  # 默認值
        
        if logic is not None:
            dim2 = "w" if self.combo2Dimension.currentText() == tr("寬") else "h"
            op2 = op1_map[self.combo2Operator.currentText()]
            val2 = self.spin2Value.value()
            condition2 = [dim2, op2, val2]
        
        # 保存參數以備下次使用
        FilterSlicesDialog.last_params = {
            "range": target,
            "condition1": {"dimension": dim1, "operator": op1, "value": val1},
            "logic": logic,
            "condition2": {"dimension": dim2, "operator": op2, "value": val2}
        }
        
        return target, condition1, logic, condition2


class CheckUpdateDialog(QDialog):
    def __init__(self, current_version, parent=None, update_text=None):
        super().__init__(parent)
        self.setWindowTitle(tr("檢査更新"))
        layout = QVBoxLayout(self)
        # 若 update_text 未傳入則嘗試取得更新資訊
        if update_text is None:
            try:
                response = urllib.request.urlopen("https://vistudium.top/gouken/UPDATE")
                update_text = response.read().decode("utf-8")
            except Exception as e:
                update_text = tr("無法取得更新資訊：") + str(e)
        lines = update_text.splitlines()
        latest_version = lines[0] if lines else ""
        if is_newer_version(current_version, latest_version):
            message = tr('🔔 有版本更新：{0}\n訪問官網獲取更新。').format(latest_version)
            msgLabel = QLabel(message, self)
            msgLabel.setOpenExternalLinks(True)
            layout.addWidget(msgLabel)
            textEdit = QTextEdit(self)
            textEdit.setReadOnly(True)
            textEdit.setPlainText(update_text)
            textEdit.setFixedWidth(500)
            layout.addWidget(textEdit)
            btnLayout = QHBoxLayout()
            visitBtn = QPushButton(tr("訪問官網"), self)
            visitBtn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://vistudium.top/gouken/")))
            btnLayout.addWidget(visitBtn)
            okBtn = QPushButton(tr("確定"), self)
            okBtn.clicked.connect(self.accept)
            btnLayout.addWidget(okBtn)
            layout.addLayout(btnLayout)
            QApplication.beep()
        else:
            msgLabel = QLabel(tr("🎉 目前已是最新版！"), self)
            layout.addWidget(msgLabel)
            btnLayout = QHBoxLayout()
            okBtn = QPushButton(tr("確定"), self)
            okBtn.clicked.connect(self.accept)
            btnLayout.addWidget(okBtn)
            layout.addLayout(btnLayout)
            QApplication.beep()


class BatchRenameDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("批量重命名"))
        mainLayout = QVBoxLayout(self)
        topLayout = QHBoxLayout()
        self.btnImport = QPushButton(tr("導入txt"), self)
        self.btnImport.clicked.connect(self.importTxt)
        topLayout.addWidget(self.btnImport)
        mainLayout.addLayout(topLayout)
        self.textEdit = QTextEdit(self)
        mainLayout.addWidget(self.textEdit)
        bottomLayout = QHBoxLayout()
        bottomLayout.addStretch()
        self.btnConfirm = QPushButton(tr("確定"), self)
        self.btnConfirm.clicked.connect(self.accept)
        bottomLayout.addWidget(self.btnConfirm)
        mainLayout.addLayout(bottomLayout)
        
    def importTxt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, tr("選擇txt文件"), "", "Text Files (*.txt)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.textEdit.setPlainText(content)
            except Exception as e:
                QMessageBox.warning(self, tr("錯誤"), tr('無法讀取文件: {0}').format(e))
    
    def getRenameLines(self):
        lines = self.textEdit.toPlainText().splitlines()
        return [line.strip() for line in lines if line.strip()]


class JsonImportPresetDialog(QDialog):
    def __init__(self, currentPreset=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("json導入預設"))
        layout = QFormLayout(self)
        self.spinOffsetX = QSpinBox(self)
        self.spinOffsetX.setRange(-100, 100)
        self.spinOffsetX.setValue(2 if currentPreset is None else currentPreset.get("offset_x", 2))
        self.spinOffsetY = QSpinBox(self)
        self.spinOffsetY.setRange(-100, 100)
        self.spinOffsetY.setValue(3 if currentPreset is None else currentPreset.get("offset_y", 3))
        
        # 勾選是否啓用切片篩除
        self.checkFilter = QCheckBox(tr("進行切片篩除"), self)
        self.checkFilter.setChecked(False if currentPreset is None else currentPreset.get("filtering", False))
        
        # 條件一
        condition1Layout = QHBoxLayout()
        self.combo1Dimension = QComboBox(self)
        self.combo1Dimension.addItems([tr("寬"), tr("高")])
        if currentPreset and currentPreset.get("condition1"):
            self.combo1Dimension.setCurrentText(tr("寬") if currentPreset["condition1"]["dimension"] == "w" else tr("高"))
        else:
            self.combo1Dimension.setCurrentText(tr("寬"))
        
        self.combo1Operator = QComboBox(self)
        self.combo1Operator.addItems([tr("大於"), tr("等於"), tr("小於")])
        op_map = {"greater": tr("大於"), "equal": tr("等於"), "less": tr("小於")}
        if currentPreset and currentPreset.get("condition1"):
            self.combo1Operator.setCurrentText(op_map.get(currentPreset["condition1"]["operator"], tr("大於")))
        else:
            self.combo1Operator.setCurrentText(tr("大於"))
        
        self.spin1Value = QSpinBox(self)
        self.spin1Value.setRange(1, 10000)
        if currentPreset and currentPreset.get("condition1"):
            self.spin1Value.setValue(currentPreset["condition1"]["value"])
        else:
            self.spin1Value.setValue(100)
        self.spin1Value.setSuffix(" px")
        
        condition1Layout.addWidget(self.combo1Dimension)
        condition1Layout.addWidget(self.combo1Operator)
        condition1Layout.addWidget(self.spin1Value)
        
        # 篩除邏輯
        logicLayout = QHBoxLayout()
        self.checkOr = QCheckBox(tr("或"), self)
        self.checkAnd = QCheckBox(tr("和"), self)
        
        # 設置初始狀態
        if currentPreset and currentPreset.get("logic") == "or":
            self.checkOr.setChecked(True)
        elif currentPreset and currentPreset.get("logic") == "and":
            self.checkAnd.setChecked(True)
        
        # 連接事件處理
        self.checkOr.stateChanged.connect(self.onLogicChanged)
        self.checkAnd.stateChanged.connect(self.onLogicChanged)
        
        logicLayout.addWidget(self.checkOr)
        logicLayout.addWidget(self.checkAnd)
        
        # 條件二
        condition2Layout = QHBoxLayout()
        self.combo2Dimension = QComboBox(self)
        self.combo2Dimension.addItems([tr("寬"), tr("高")])
        if currentPreset and currentPreset.get("condition2"):
            self.combo2Dimension.setCurrentText(tr("高") if currentPreset["condition2"]["dimension"] == "h" else tr("寬"))
        else:
            self.combo2Dimension.setCurrentText(tr("高"))
        
        self.combo2Operator = QComboBox(self)
        self.combo2Operator.addItems([tr("大於"), tr("等於"), tr("小於")])
        if currentPreset and currentPreset.get("condition2"):
            self.combo2Operator.setCurrentText(op_map.get(currentPreset["condition2"]["operator"], tr("大於")))
        else:
            self.combo2Operator.setCurrentText(tr("大於"))
        
        self.spin2Value = QSpinBox(self)
        self.spin2Value.setRange(1, 10000)
        if currentPreset and currentPreset.get("condition2"):
            self.spin2Value.setValue(currentPreset["condition2"]["value"])
        else:
            self.spin2Value.setValue(100)
        self.spin2Value.setSuffix(" px")
        
        condition2Layout.addWidget(self.combo2Dimension)
        condition2Layout.addWidget(self.combo2Operator)
        condition2Layout.addWidget(self.spin2Value)
        
        # 設置篩選控件的啟用狀態
        self.updateFilterState()
        self.checkFilter.stateChanged.connect(self.updateFilterState)
        
        # 設置條件二的初始啟用狀態
        self.updateCondition2State()
        
        # 組合所有項目
        layout.addRow(tr("向右移動："), self.spinOffsetX)
        layout.addRow(tr("向下移動："), self.spinOffsetY)
        layout.addRow(self.checkFilter)
        layout.addRow(tr("條件一："), condition1Layout)
        layout.addRow(tr("篩除邏輯："), logicLayout)
        layout.addRow(tr("條件二："), condition2Layout)
        btnBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        btnBox.accepted.connect(self.accept)
        btnBox.rejected.connect(self.reject)
        layout.addRow(btnBox)
    
    def updateFilterState(self):
        # 當未勾選「進行切片篩除」時，禁用所有篩選相關控件
        enabled = self.checkFilter.isChecked()
        self.combo1Dimension.setEnabled(enabled)
        self.combo1Operator.setEnabled(enabled)
        self.spin1Value.setEnabled(enabled)
        self.checkOr.setEnabled(enabled)
        self.checkAnd.setEnabled(enabled)
        
        # 條件二的啟用狀態需要同時考慮篩選總開關和邏輯操作符
        self.updateCondition2State()
    
    def onLogicChanged(self):
        # 確保最多只能選擇一個邏輯操作符
        sender = self.sender()
        if sender == self.checkOr and self.checkOr.isChecked():
            self.checkAnd.setChecked(False)
        elif sender == self.checkAnd and self.checkAnd.isChecked():
            self.checkOr.setChecked(False)
        
        self.updateCondition2State()
    
    def updateCondition2State(self):
        # 條件二需要同時滿足：篩選開關啟用 AND 有邏輯操作符選擇
        filter_enabled = self.checkFilter.isChecked()
        has_logic = self.checkOr.isChecked() or self.checkAnd.isChecked()
        condition2_enabled = filter_enabled and has_logic
        
        self.combo2Dimension.setEnabled(condition2_enabled)
        self.combo2Operator.setEnabled(condition2_enabled)
        self.spin2Value.setEnabled(condition2_enabled)
        
    def getValues(self):
        # 獲取第一個條件
        dim1 = "w" if self.combo1Dimension.currentText() == tr("寬") else "h"
        op1_map = {tr("大於"): "greater", tr("等於"): "equal", tr("小於"): "less"}
        op1 = op1_map[self.combo1Operator.currentText()]
        val1 = self.spin1Value.value()
        
        # 獲取邏輯操作符
        logic = None
        if self.checkOr.isChecked():
            logic = "or"
        elif self.checkAnd.isChecked():
            logic = "and"
        
        # 獲取第二個條件（如果有邏輯操作符）
        dim2 = "h"  # 默認值
        op2 = "greater"  # 默認值
        val2 = 100  # 默認值
        
        if logic is not None:
            dim2 = "w" if self.combo2Dimension.currentText() == tr("寬") else "h"
            op2 = op1_map[self.combo2Operator.currentText()]
            val2 = self.spin2Value.value()
        
        return {
            "offset_x": self.spinOffsetX.value(),
            "offset_y": self.spinOffsetY.value(),
            "filtering": self.checkFilter.isChecked(),
            "condition1": {"dimension": dim1, "operator": op1, "value": val1},
            "logic": logic,
            "condition2": {"dimension": dim2, "operator": op2, "value": val2}
        }
