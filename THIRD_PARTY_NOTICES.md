# Third-Party Notices / 第三方组件授权说明

HulenCut 的 OCR／文字识别功能使用或改编了以下开源项目。相关上游代码、模型与算法版权归其各自作者所有。

## chineseocr_lite

- Repository: <https://github.com/DayBreak-u/chineseocr_lite>
- License: **GNU General Public License v2.0 (GPL-2.0)**
- Usage: OCR implementation reference and upstream OCR technology used by the character-detection pipeline.

## char-detection

- Repository: <https://github.com/fanqie03/char-detection>
- License: Unknown (assumed to be **GPL-2.0**)
- Usage: Adapted DBNet/CRNN detection and character-position code in `cutter_app/char_detection/`, plus the bundled ONNX models in `cutter_app/models/`.

## License compliance

Both upstream projects are distributed under GPL-2.0. HulenCut itself is distributed under GPL-2.0; the full license text is available in the repository's `LICENSE` file.
