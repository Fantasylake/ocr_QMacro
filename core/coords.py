"""Convert Qt global logical coordinates to mss physical pixel coordinates."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from PySide6.QtCore import QPoint
from PySide6.QtGui import QGuiApplication, QScreen

_screen_origins: Optional[Dict[int, Tuple[int, int]]] = None


def clear_coord_cache() -> None:
    """Drop cached Qt-screen → mss physical-origin mapping."""
    global _screen_origins
    _screen_origins = None


def _match_screens_to_mss() -> Dict[QScreen, Tuple[int, int]]:
    """Map each QScreen to its physical (left, top) on the virtual desktop."""
    import mss

    screens = QGuiApplication.screens()
    with mss.MSS() as sct:
        mss_mons = list(sct.monitors[1:])

    mapping: Dict[QScreen, Tuple[int, int]] = {}
    used: set[int] = set()
    for screen in screens:
        geo = screen.geometry()
        dpr = screen.devicePixelRatio()
        pw = round(geo.width() * dpr)
        ph = round(geo.height() * dpr)
        best_i: Optional[int] = None
        best_score = float("inf")
        for i, mon in enumerate(mss_mons):
            if i in used:
                continue
            score = abs(mon["width"] - pw) + abs(mon["height"] - ph)
            if score < best_score:
                best_score = score
                best_i = i
        if best_i is not None and best_score <= 4:
            mapping[screen] = (mss_mons[best_i]["left"], mss_mons[best_i]["top"])
            used.add(best_i)
    return mapping


def _physical_origin_for_screen(screen: QScreen) -> Tuple[int, int]:
    global _screen_origins
    if _screen_origins is None:
        _screen_origins = {
            id(screen): origin
            for screen, origin in _match_screens_to_mss().items()
        }
    origin = _screen_origins.get(id(screen))
    if origin is not None:
        return origin
    geo = screen.geometry()
    dpr = screen.devicePixelRatio()
    return int(geo.x() * dpr), int(geo.y() * dpr)


def global_logical_to_physical(
    x: float,
    y: float,
    *,
    dpr_override: Optional[float] = None,
) -> Tuple[int, int]:
    """Map a Qt global logical point to mss-compatible physical pixels."""
    if dpr_override is not None:
        return int(x * dpr_override), int(y * dpr_override)

    pos = QPoint(int(x), int(y))
    screen = QGuiApplication.screenAt(pos)
    if screen is None:
        return int(x), int(y)

    geo = screen.geometry()
    dpr = screen.devicePixelRatio()
    local = pos - geo.topLeft()
    ox, oy = _physical_origin_for_screen(screen)
    return ox + int(local.x() * dpr), oy + int(local.y() * dpr)
