"""Smoke tests for the RapidOCR backend.

These tests are *skip-aware*: they run only when RapidOCR is installed.
The goal is to:

1. Verify that ``recognize_text`` returns non-empty Chinese text on a
   rendered test image.
2. Verify that two passes over the same image are equal under
   ``texts_equal`` — this is the whole point of the baseline-OCR
   feature, and it must hold across passes.
3. Verify that the engine reports its name correctly.

We deliberately do NOT assert exact OCR text equality across runs of
the test on different machines — RapidOCR's detection can produce
slightly different whitespace/segmentation on the same image across
OS/font combinations.
"""
from pathlib import Path

import pytest

from core.ocr import backend_name
from core.matcher import texts_equal


FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "ocr_sample.png"
SIMPLE = FIXTURES / "ocr_simple.png"


def _has_rapid() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


# Skip the whole module if RapidOCR isn't installed.
pytestmark = pytest.mark.skipif(
    not _has_rapid(),
    reason="rapidocr-onnxruntime not installed",
)


@pytest.fixture(scope="module")
def png_sample() -> bytes:
    return SAMPLE.read_bytes()


@pytest.fixture(scope="module")
def png_simple() -> bytes:
    return SIMPLE.read_bytes()


def test_backend_name_is_rapid():
    assert backend_name() == "rapid"


def test_recognize_text_returns_chinese(png_sample):
    from core.ocr import recognize_text
    text = recognize_text(png_sample)
    assert text, "OCR returned empty string"
    # The fixture contains the word 成功 ("success") which is a hard
    # requirement for the keyword match feature.
    assert "成功" in text, f"Expected 成功 in OCR output, got: {text!r}"


def test_two_passes_are_equal(png_sample):
    """Two OCR passes over the same image must be equal under
    texts_equal. This is the core baseline-OCR invariant."""
    from core.ocr import recognize_text
    a = recognize_text(png_sample)
    b = recognize_text(png_sample)
    assert texts_equal(a, b), f"OCR not stable:\n  a: {a!r}\n  b: {b!r}"


def test_different_images_differ(png_sample, png_simple):
    """Sanity: two genuinely different images must not be equal."""
    from core.ocr import recognize_text
    a = recognize_text(png_sample)
    b = recognize_text(png_simple)
    assert not texts_equal(a, b), (
        f"Different images produced equal OCR text:\n  a: {a!r}\n  b: {b!r}"
    )
