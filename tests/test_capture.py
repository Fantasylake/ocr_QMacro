import pytest
from core.capture import capture_region, CaptureError

def test_capture_returns_bytes():
    png = capture_region({"top": 0, "left": 0, "width": 100, "height": 100})
    assert isinstance(png, (bytes, bytearray))
    assert len(png) > 0
    assert png[:8] == b"\x89PNG\r\n\x1a\n"

def test_capture_invalid_bbox_raises():
    with pytest.raises(CaptureError):
        capture_region({"top": -1, "left": 0, "width": 0, "height": 0})
