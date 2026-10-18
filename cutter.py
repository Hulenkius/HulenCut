"""HulenCut compatibility entry point.

The implementation lives in the :mod:`cutter_app` package. Public classes are
re-exported here to keep existing imports such as ``from cutter import
MainWindow`` working.
"""
from cutter_app.app import main
from cutter_app.dialogs import (
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
from cutter_app.graphics import SliceListWidget, SliceRect, SliceView
from cutter_app.main_window import MainWindow
from cutter_app.panels import (
    AlignDistributeWidget,
    AutoProcessPanel,
    FindWidget,
    PreviewPanel,
    SliceDimensionWidget,
    StraightenWidget,
)
from cutter_app.scripting import ScriptRecorder
from cutter_app.utils import resource_path

__all__ = [
    "AlignDistributeWidget",
    "AutoProcessPanel",
    "BatchRenameDialog",
    "CheckUpdateDialog",
    "DivideSlicesDialog",
    "FilterSlicesDialog",
    "FindWidget",
    "JsonImportPresetDialog",
    "MainWindow",
    "MoveSlicesDialog",
    "NormalizeSlicesDialog",
    "PreviewPanel",
    "ScaleProjectDialog",
    "ScaleSlicesDialog",
    "ScriptRecorder",
    "SliceDimensionWidget",
    "SliceListWidget",
    "SliceRect",
    "SliceView",
    "StraightenWidget",
    "TableDetectDialog",
    "main",
    "resource_path",
]

if __name__ == "__main__":
    raise SystemExit(main())
