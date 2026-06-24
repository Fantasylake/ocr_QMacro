"""Tests for virtual-desktop bounds checks."""
from unittest.mock import patch

from core.capture import bbox_within_desktop, point_within_desktop


def test_bbox_within_desktop_accepts_in_bounds():
    with patch("core.capture.virtual_desktop_bounds", return_value=(0, 0, 1920, 1080)):
        ok, msg = bbox_within_desktop({"top": 100, "left": 200, "width": 300, "height": 400})
    assert ok is True
    assert msg == ""


def test_bbox_within_desktop_rejects_dev_machine_coords_on_1080p():
    """Coords from a 3072x1920 setup must fail on a 1920x1080 desktop."""
    with patch("core.capture.virtual_desktop_bounds", return_value=(0, 0, 1920, 1080)):
        ok, msg = bbox_within_desktop({"top": 648, "left": 681, "width": 1552, "height": 197})
    assert ok is False
    assert "超出当前屏幕" in msg


def test_point_within_desktop_rejects_off_screen():
    with patch("core.capture.virtual_desktop_bounds", return_value=(0, 0, 1920, 1080)):
        ok, msg = point_within_desktop(2106, 542)
    assert ok is False
    assert "2106" in msg
