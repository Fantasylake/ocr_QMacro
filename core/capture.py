from __future__ import annotations

import io
from typing import Mapping

import mss
from PIL import Image, ImageStat


class CaptureError(RuntimeError):
    pass


def virtual_desktop_bounds() -> tuple[int, int, int, int]:
    """Return ``(left, top, width, height)`` of the virtual desktop in physical pixels."""
    with mss.MSS() as sct:
        mon = sct.monitors[0]
    return int(mon["left"]), int(mon["top"]), int(mon["width"]), int(mon["height"])


def bbox_within_desktop(bbox: Mapping[str, int]) -> tuple[bool, str]:
    """Check whether a capture bbox lies fully inside the current virtual desktop."""
    try:
        left = int(bbox["left"])
        top = int(bbox["top"])
        width = int(bbox["width"])
        height = int(bbox["height"])
    except (KeyError, TypeError, ValueError):
        return False, f"invalid bbox: {bbox}"

    desk_left, desk_top, desk_w, desk_h = virtual_desktop_bounds()
    desk_right = desk_left + desk_w
    desk_bottom = desk_top + desk_h
    right = left + width
    bottom = top + height

    if (
        left < desk_left
        or top < desk_top
        or right > desk_right
        or bottom > desk_bottom
    ):
        return (
            False,
            "监控区域超出当前屏幕范围 "
            f"({desk_w}x{desk_h})。坐标是在另一台电脑/缩放下保存的，"
            "请在本机重新「框选区域」和「拾取」点击点。",
        )
    return True, ""


def point_within_desktop(x: int, y: int) -> tuple[bool, str]:
    """Check whether a click point lies inside the current virtual desktop."""
    desk_left, desk_top, desk_w, desk_h = virtual_desktop_bounds()
    desk_right = desk_left + desk_w
    desk_bottom = desk_top + desk_h
    if desk_left <= x < desk_right and desk_top <= y < desk_bottom:
        return True, ""
    return (
        False,
        f"坐标 ({x}, {y}) 超出当前屏幕 ({desk_w}x{desk_h})，"
        "请在本机重新拾取。",
    )


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


def png_mean_luminance(png_bytes: bytes) -> float:
    """Return average grayscale brightness (0-255) for capture diagnostics."""
    if not png_bytes:
        return 0.0
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    stat = ImageStat.Stat(img)
    return float(stat.mean[0])
