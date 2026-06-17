"""OCR adapter backed by RapidOCR (ONNX Runtime).

Single backend; ``recognize_text(png_bytes) -> str`` is the entire
public surface the rest of the app sees. The backend is selected at
import time and can be inspected via ``backend_name()``; the
``OCR_BACKEND`` env var is accepted for completeness but only the
``rapid`` (default) and ``auto`` values are meaningful now.
"""
from __future__ import annotations

import io
import time
from typing import Any, List, Optional

from PIL import Image


# ---------------------------------------------------------------- engine
class _RapidEngine:
    """Thin wrapper around RapidOCR that normalises output to ``\n``-joined text."""

    name = "rapid"

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR
        # RapidOCR's __init__ is fast and offline-safe — the wheel
        # ships model files in-site, no network is needed.
        self._engine = RapidOCR()

    def recognize(self, png_bytes: bytes) -> str:
        # RapidOCR accepts raw bytes directly; no PIL/numpy conversion needed.
        result, _elapse = self._engine(png_bytes)
        if not result:
            return ""
        # Each item is [box_points, text, confidence]
        texts: List[str] = [str(item[1]) for item in result]
        return "\n".join(texts)


_engine: Optional[Any] = None
_engine_init_ms: float = 0.0


def _get_engine() -> _RapidEngine:
    """Lazy-init the engine on first OCR call.

    Lazy because RapidOCR's first inference pays a one-time onnxruntime
    warm-up cost (a few hundred ms) we don't want to block GUI startup.
    Baseline establishment triggers init.
    """
    global _engine, _engine_init_ms
    if _engine is None:
        t0 = time.perf_counter()
        _engine = _RapidEngine()
        _engine_init_ms = (time.perf_counter() - t0) * 1000
    return _engine  # type: ignore[return-value]


# ---------------------------------------------------------------- public API
def backend_name() -> str:
    """Return the active backend name. Always ``"rapid"``."""
    return "rapid"


def get_reader() -> _RapidEngine:
    """Backwards-compatible accessor for the engine instance.

    Prefer ``recognize_text`` for actual OCR; this is exposed so tests
    and diagnostics can introspect the engine.
    """
    return _get_engine()


def recognize_text(png_bytes: bytes) -> str:
    """Run OCR on PNG bytes; return concatenated recognized text (one line per detection)."""
    return _get_engine().recognize(png_bytes)


def engine_init_ms() -> float:
    """Time spent constructing the OCR engine, in milliseconds. 0 before first call."""
    return _engine_init_ms
