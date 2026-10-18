"""Project paths and resource helpers."""
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative_path: str) -> str:
    """Return an absolute path both in development and in a PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    else:
        base = Path(__file__).resolve().parent.parent
    return str(base / relative_path)
