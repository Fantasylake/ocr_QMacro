"""Tests for Qt logical -> mss physical coordinate conversion."""
import sys

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from core.coords import clear_coord_cache, global_logical_to_physical


@pytest.fixture
def app():
    a = QApplication.instance() or QApplication(sys.argv)
    clear_coord_cache()
    yield a
    clear_coord_cache()


def test_dpr_override_scales_global(app):
    x, y = global_logical_to_physical(100, 200, dpr_override=1.75)
    assert (x, y) == (175, 350)


def test_primary_screen_matches_mss(app):
    """On a single monitor, screen-relative conversion matches global * DPR."""
    screen = app.primaryScreen()
    dpr = screen.devicePixelRatio()
    x, y = global_logical_to_physical(500, 300)
    assert (x, y) == (int(500 * dpr), int(300 * dpr))
