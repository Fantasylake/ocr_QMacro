from __future__ import annotations

import io
from typing import Mapping

import mss
from PIL import Image


class CaptureError(RuntimeError):
    pass


def capture_region(bbox: Mapping[str, int]) -> bytes:
    """Capture a screen region and return PNG bytes.

    bbox requires keys: top, left, width, height (all >= 0).
    """
    try:
        top = int(bbox["top"])
        left = int(bbox["left"])
        width = int(bbox["width"])
        height = int(bbox["height"])
    except (KeyError, TypeError, ValueError) as e:
        raise CaptureError(f"invalid bbox: {bbox}") from e
    if width <= 0 or height <= 0 or top < 0 or left < 0:
        raise CaptureError(f"invalid bbox dimensions: {bbox}")

    region = {"top": top, "left": left, "width": width, "height": height}
    try:
        with mss.MSS() as sct:
            shot = sct.grab(region)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    except Exception as e:
        raise CaptureError(f"screenshot failed: {e}") from e

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
