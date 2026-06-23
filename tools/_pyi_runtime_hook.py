"""PyInstaller runtime hook: make bundled RapidOCR models findable when frozen.

Problem:
  RapidOCR's rapid_ocr_api.py does:
      sys.path.append(str(Path(__file__).resolve().parent))
      importlib.import_module("ch_ppocr_v3_det")

  In a frozen build, ``__file__`` resolves to a path inside the extracted
  _MEIPASS temp directory, but sys.path does NOT contain that directory,
  so the import fails with:
      module 'ch_ppocr_v3_det' has no attribute 'TextDetector'

Fix:
  Prepend the _MEIPASS rapidocr_onnxruntime directory to sys.path so that
  ``importlib.import_module("ch_ppocr_v3_det")`` finds the submodule.
"""
from __future__ import annotations

import os
import sys


def _patch_rapidocr_paths() -> None:
    if not getattr(sys, "frozen", False):
        return

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is None:
        return

    # The rapidocr_onnxruntime package is extracted to this directory.
    rapidocr_dir = os.path.join(meipass, "rapidocr_onnxruntime")

    # Only patch if the directory actually exists in the extraction root.
    if not os.path.isdir(rapidocr_dir):
        return

    # Prepend so it is searched before any system site-packages.
    if rapidocr_dir not in sys.path:
        sys.path.insert(0, rapidocr_dir)


_patch_rapidocr_paths()
del _patch_rapidocr_paths
