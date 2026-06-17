"""Tests for picker.py internal helpers (geometry only, no GUI)."""
from ui.picker import _norm_rect, PickedRegion


def test_norm_rect_normal_direction():
    r = _norm_rect(100, 50, 300, 200)
    assert r == PickedRegion(top=50, left=100, width=200, height=150)


def test_norm_rect_reversed_direction():
    r = _norm_rect(300, 200, 100, 50)
    assert r == PickedRegion(top=50, left=100, width=200, height=150)


def test_norm_rect_zero_size():
    r = _norm_rect(100, 100, 100, 100)
    assert r == PickedRegion(top=100, left=100, width=0, height=0)
