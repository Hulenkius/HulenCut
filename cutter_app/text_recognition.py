"""Character-level OCR slicing support.

The detection backend is adapted from the user-supplied ``char-detection``
project (DBNet + CRNN). All heavyweight OCR imports are deliberately lazy so
that HulenCut still starts normally when the optional OCR dependencies are not
installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from .utils import resource_path


HORIZONTAL = "horizontal"
VERTICAL = "vertical"
VALID_ORIENTATIONS = (HORIZONTAL, VERTICAL)


class TextRecognitionUnavailableError(RuntimeError):
    """Raised when the optional OCR runtime or model files are unavailable."""


class TextRecognitionError(RuntimeError):
    """Raised when text recognition itself fails."""


@dataclass(frozen=True)
class RecognizedCharacter:
    """A single recognised character and its quadrilateral in image space."""

    char: str
    bbox: tuple[tuple[float, float], ...]
    line_index: int = 0
    char_index: int = 0

    def bounds(self) -> tuple[float, float, float, float]:
        """Return an axis-aligned ``(x, y, width, height)`` bounding box."""
        points = np.asarray(self.bbox, dtype=np.float32)
        x1 = float(np.min(points[:, 0]))
        y1 = float(np.min(points[:, 1]))
        x2 = float(np.max(points[:, 0]))
        y2 = float(np.max(points[:, 1]))
        return x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)


_detector = None


def _model_path(filename: str) -> str:
    path = Path(resource_path(f"cutter_app/models/{filename}"))
    if not path.is_file():
        raise TextRecognitionUnavailableError(f"找不到文字識別模型：{path}")
    return str(path)


def _get_detector():
    """Create (once) and return the DBNet/CRNN detector."""
    global _detector
    if _detector is not None:
        return _detector

    try:
        import onnxruntime as ort

        ort.set_default_logger_severity(3)
        from .char_detection.crnn import CRNNHandle
        from .char_detection.dbnet.dbnet_infer import DBNET
    except ImportError as exc:
        raise TextRecognitionUnavailableError(
            "文字識別功能需要額外依賴：onnxruntime、Pillow、shapely、pyclipper。\n"
            "若已安裝，請完全關閉並重新啟動 HulenCut（ONNX Runtime 必須在 Qt 前載入）。\n"
            f"缺少的模組：{exc.name or exc}"
        ) from exc

    _detector = _TextDetector(
        DBNET(_model_path("dbnet.onnx")),
        CRNNHandle(_model_path("crnn_lite_lstm.onnx")),
    )
    return _detector


class _TextDetector:
    """Small adapter around the vendored char-detection implementation."""

    def __init__(self, dbnet, crnn) -> None:
        self.dbnet = dbnet
        self.crnn = crnn

    def recognize(self, image_rgb: np.ndarray, short_size: int = 960):
        from PIL import Image

        from .char_detection.utils import get_rotate_crop_image, sorted_boxes

        boxes_list, score_list = self.dbnet.process(
            np.asarray(image_rgb).astype(np.uint8), short_size=short_size
        )
        results = []
        boxes_list = sorted_boxes(np.asarray(boxes_list))
        for box, score in zip(boxes_list, score_list):
            crop = get_rotate_crop_image(
                np.asarray(image_rgb), np.asarray(box).astype(np.float32)
            )
            part_image = Image.fromarray(crop).convert("RGB")
            result = self.crnn.predict_rbg(part_image, np.array(box))
            results.append(
                {"bbox": np.asarray(box), "result": result, "score": float(score)}
            )
        return results

    def recognize_line_text(self, image_rgb: np.ndarray) -> str:
        """Recognise a crop directly with CRNN as a fallback."""
        from PIL import Image

        height, width = image_rgb.shape[:2]
        bbox = np.asarray(
            [[0, 0], [width, 0], [width, height], [0, height]],
            dtype=np.float32,
        )
        part_image = Image.fromarray(image_rgb).convert("RGB")
        result = self.crnn.predict_rbg(part_image, bbox)
        return str(result.get("line_pred", "")).strip()


def _line_center(bbox: np.ndarray) -> tuple[float, float]:
    points = np.asarray(bbox, dtype=np.float32).reshape(-1, 2)
    return float(np.mean(points[:, 0])), float(np.mean(points[:, 1]))


def _order_lines(results: Sequence[dict], orientation: str) -> list[dict]:
    """Order OCR lines in the reading direction selected by the user."""
    if orientation == VERTICAL:
        return sorted(
            results,
            key=lambda item: (
                -_line_center(item["bbox"])[0],
                _line_center(item["bbox"])[1],
            ),
        )
    return sorted(
        results,
        key=lambda item: (
            _line_center(item["bbox"])[1],
            _line_center(item["bbox"])[0],
        ),
    )


def _box_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


def recognize_characters(
    image_bgr: np.ndarray,
    orientation: str = HORIZONTAL,
    short_size: int = 960,
) -> list[RecognizedCharacter]:
    """Recognise text and return one bounding box for every visible character."""
    if orientation not in VALID_ORIENTATIONS:
        raise ValueError(f"Unknown text orientation: {orientation!r}")
    if image_bgr is None:
        raise TextRecognitionError("沒有可識別的圖片")
    image = np.asarray(image_bgr)
    if image.ndim == 2:
        import cv2

        image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    elif image.ndim == 3 and image.shape[2] == 3:
        import cv2

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    elif image.ndim == 3 and image.shape[2] == 4:
        import cv2

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
    else:
        raise TextRecognitionError("不支援的圖片格式")

    height, width = image_rgb.shape[:2]
    if height == 0 or width == 0:
        raise TextRecognitionError("圖片尺寸為零")

    try:
        results = _get_detector().recognize(image_rgb, short_size=short_size)
    except TextRecognitionUnavailableError:
        raise
    except Exception as exc:
        raise TextRecognitionError(str(exc)) from exc

    characters: list[RecognizedCharacter] = []
    seen: list[tuple[str, tuple[float, float, float, float]]] = []
    for line_index, line in enumerate(_order_lines(results, orientation)):
        char_items = (line.get("result") or {}).get("char_list") or []
        for char_index, char_item in enumerate(char_items):
            char = str(char_item.get("char", ""))
            if not char or char.isspace():
                continue
            raw_bbox = char_item.get("bbox")
            if raw_bbox is None:
                continue
            points = np.asarray(raw_bbox, dtype=np.float32).reshape(-1, 2)
            if points.shape[0] < 4:
                continue

            x1 = max(0.0, float(np.min(points[:, 0])))
            y1 = max(0.0, float(np.min(points[:, 1])))
            x2 = min(float(width), float(np.max(points[:, 0])))
            y2 = min(float(height), float(np.max(points[:, 1])))
            if x2 - x1 < 1.0 or y2 - y1 < 1.0:
                continue

            bounds = (x1, y1, x2 - x1, y2 - y1)
            if any(
                previous_char == char and _box_iou(previous_bounds, bounds) > 0.92
                for previous_char, previous_bounds in seen
            ):
                continue
            seen.append((char, bounds))
            characters.append(
                RecognizedCharacter(
                    char=char,
                    bbox=tuple((float(x), float(y)) for x, y in points.tolist()),
                    line_index=line_index,
                    char_index=char_index,
                )
            )
    return characters


def recognize_text(image_bgr: np.ndarray, short_size: int | None = None) -> str:
    """Recognise the text contained in one image crop.

    DBNet is used to find text lines first; if it finds nothing (common for
    tightly cropped single characters), CRNN is applied directly as a fallback.
    """
    if image_bgr is None:
        raise TextRecognitionError("沒有可識別的圖片")
    image = np.asarray(image_bgr)
    if image.ndim == 2:
        import cv2

        image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    elif image.ndim == 3 and image.shape[2] == 3:
        import cv2

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    elif image.ndim == 3 and image.shape[2] == 4:
        import cv2

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
    else:
        raise TextRecognitionError("不支援的圖片格式")

    height, width = image_rgb.shape[:2]
    if height == 0 or width == 0:
        raise TextRecognitionError("圖片尺寸為零")

    if short_size is None:
        longest = max(height, width)
        if longest <= 160:
            short_size = 320
        elif longest <= 512:
            short_size = 640
        else:
            short_size = 960

    try:
        detector = _get_detector()
        results = detector.recognize(image_rgb, short_size=short_size)
        pieces = []
        for line in _order_lines(results, HORIZONTAL):
            line_text = str((line.get("result") or {}).get("line_pred", "")).strip()
            if line_text:
                pieces.append(line_text)
        if pieces:
            return " ".join(pieces)
        return detector.recognize_line_text(image_rgb)
    except TextRecognitionUnavailableError:
        raise
    except Exception as exc:
        raise TextRecognitionError(str(exc)) from exc


def ocr_dependencies_available() -> bool:
    """Return whether all runtime packages needed by the OCR backend exist."""
    import importlib.util

    return all(
        importlib.util.find_spec(name) is not None
        for name in ("onnxruntime", "PIL", "shapely", "pyclipper")
    )
