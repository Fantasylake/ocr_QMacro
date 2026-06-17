from __future__ import annotations

import io
from typing import List, Optional

import easyocr
import numpy as np
from PIL import Image

_reader: Optional["easyocr.Reader"] = None


def get_reader(gpu: bool = False) -> "easyocr.Reader":
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["ch_sim", "en"], gpu=gpu, verbose=False)
    return _reader


def recognize_text(png_bytes: bytes) -> str:
    """Run OCR on PNG bytes; return concatenated recognized text (one line per detection)."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    arr = np.array(img)
    reader = get_reader()
    results: List = reader.readtext(arr, detail=0, paragraph=False)
    return "\n".join(str(r) for r in results)
