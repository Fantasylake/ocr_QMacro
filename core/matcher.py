from __future__ import annotations

import re
from typing import Iterable, Tuple


_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize OCR text for change detection.

    Collapses all whitespace (spaces, tabs, newlines) to a single space
    and strips both ends. This makes "a b" / "a\\nb" / " a   b " all
    compare equal — necessary because EasyOCR's line breaks shift around
    even when the visible content is unchanged.
    """
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()


def texts_equal(a: str, b: str) -> bool:
    """Whitespace-insensitive equality for OCR change detection."""
    return normalize_text(a) == normalize_text(b)


def match_keywords(text: str, keywords: Iterable[str]) -> Tuple[bool, str]:
    if not text or not keywords:
        return False, ""
    for raw in keywords:
        kw = raw.strip()
        if kw and kw in text:
            return True, kw
    return False, ""
