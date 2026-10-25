"""Application bootstrap."""
from __future__ import annotations

import sys


def _preload_optional_ocr_runtime() -> None:
    """Load ONNX Runtime before Qt.

    Some Windows ONNX Runtime builds fail to initialise their native extension
    if Qt has already loaded its own DLL set.  Importing the optional OCR
    runtime first avoids that conflict.  Failure is harmless: the OCR action
    will report the missing dependency when the user invokes it.
    """
    try:
        import onnxruntime as ort

        ort.set_default_logger_severity(3)
    except Exception:
        pass


_preload_optional_ocr_runtime()

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QGuiApplication, QIcon
from PyQt5.QtWidgets import QApplication

from .i18n import i18n
from .main_window import MainWindow
from .theme import theme_manager
from .utils import resource_path


def main() -> int:
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    if hasattr(QGuiApplication, "setHighDpiScaleFactorRoundingPolicy"):
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)
    app.setOrganizationName("HulenCut")
    app.setApplicationName("HulenCut")
    app.setWindowIcon(QIcon(resource_path("hulencutter.ico")))
    i18n.initialize(app)
    theme_manager.initialize(app)
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
