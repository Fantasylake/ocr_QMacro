"""Verify HiDPI scaling: picker converts logical mouse positions to physical pixels.

Background: On Windows with display scaling (e.g. 125%, 150%, 175%, 200%),
Qt reports mouse positions in logical pixels (DIPs) while mss captures
screenshots in physical pixels. If we stored logical coordinates and fed
them directly to mss, the captured region would be ~DPR times smaller
than the user selected, AND offset.

The fix: scale by devicePixelRatio at pick time so stored coordinates
are in the same space as the framebuffer.
"""
import sys
import pytest
from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QMouseEvent

from ui.picker import PickerOverlay


@pytest.fixture
def app():
    a = QApplication.instance() or QApplication(sys.argv)
    yield a


def _click(app, widget, pos: QPoint):
    press = QMouseEvent(QEvent.MouseButtonPress, pos, pos,
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, press)
    app.processEvents()


def _point_pick(app, dpr: float, logical: QPoint):
    overlay = PickerOverlay(dpr=dpr)
    overlay.set_mode("point")
    overlay.show()
    overlay.raise_()
    overlay.activateWindow()
    for _ in range(5):
        app.processEvents()
    _click(app, overlay, logical)
    for _ in range(5):
        app.processEvents()
    picked = overlay.picked_point()
    overlay.close()
    for _ in range(3):
        app.processEvents()
    return picked


def test_dpr_1_passthrough(app):
    """At DPR=1.0, logical == physical (no scaling, no conversion)."""
    assert _point_pick(app, dpr=1.0, logical=QPoint(500, 300)) == (500, 300)


def test_dpr_1_5_scales_to_physical(app):
    """At 150% scale, logical (500, 300) -> physical (750, 450)."""
    assert _point_pick(app, dpr=1.5, logical=QPoint(500, 300)) == (750, 450)


def test_dpr_1_75_user_actual_scale(app):
    """At 175% scale (the user's actual screen), logical (100, 200) -> (175, 350)."""
    assert _point_pick(app, dpr=1.75, logical=QPoint(100, 200)) == (175, 350)


def test_dpr_2_retina(app):
    """At 200% (4K Retina-style), logical (100, 100) -> physical (200, 200)."""
    assert _point_pick(app, dpr=2.0, logical=QPoint(100, 100)) == (200, 200)


def test_dpr_1_25_modern_laptops(app):
    """At 125% (a common modern laptop default), logical (400, 100) -> (500, 125)."""
    assert _point_pick(app, dpr=1.25, logical=QPoint(400, 100)) == (500, 125)
