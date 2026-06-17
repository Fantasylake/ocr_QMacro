"""Verify point-mode pick captures clicks at any screen position.

These tests use dpr=1.0 (no scaling) to keep the math simple and
focused on the picking/clicking flow. HiDPI scaling is tested
separately in test_hidpi_pick.py.
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


def _make_overlay(app, mode="point", dpr=1.0):
    overlay = PickerOverlay(dpr=dpr)
    overlay.set_mode(mode)
    overlay.show()
    app.processEvents()
    return overlay


def _click(app, widget, pos: QPoint):
    press = QMouseEvent(QEvent.MouseButtonPress, pos, pos,
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, press)
    app.processEvents()


def test_point_pick_at_bottom_left(app):
    overlay = _make_overlay(app, "point", dpr=1.0)
    _click(app, overlay, QPoint(50, 550))
    assert overlay.picked_point() == (50, 550)
    assert not overlay.isVisible()


def test_point_pick_at_right_edge(app):
    overlay = _make_overlay(app, "point", dpr=1.0)
    _click(app, overlay, QPoint(780, 300))
    assert overlay.picked_point() == (780, 300)


def test_point_pick_on_hint_bar(app):
    overlay = _make_overlay(app, "point", dpr=1.0)
    _click(app, overlay, QPoint(400, 30))
    assert overlay.picked_point() == (400, 30)
