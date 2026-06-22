from __future__ import annotations

import re
from typing import Iterable, Tuple


_WS_RE = re.compile(r"\s+")

# OCR confusables — only this single pair: 己 (jǐ) and 已 (yǐ) look
# almost identical in print and are routinely swapped by OCR engines.
# We pick 己 as the canonical glyph and map 已 -> 己 (one-way), so a
# user-configured "自己的厂房" still matches OCR output "自已的厂房".
# Do NOT make this bidirectional — 己 -> 已 -> 己 would flip-flop.
_OCR_CONFUSIONS = {"已": "己"}


def normalize_text(text: str) -> str:
    """Normalize OCR text for change detection.

    Collapses all whitespace (spaces, tabs, newlines) to a single space
    and strips both ends. This makes "a b" / "a\\nb" / " a   b " all
    compare equal — necessary because OCR engines can shift line
    breaks even when the visible content is unchanged.
    """
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()


def texts_equal(a: str, b: str) -> bool:
    """Whitespace-insensitive equality for OCR change detection."""
    return normalize_text(a) == normalize_text(b)


def _ocr_normalize(text: str) -> str:
    """Map 已 -> 己 (one-way). Idempotent. Leaves everything else alone."""
    if not text:
        return ""
    return "".join(_OCR_CONFUSIONS.get(c, c) for c in text)


def match_keywords(text: str, keywords: Iterable[str]) -> Tuple[bool, str]:
    if not text or not keywords:
        return False, ""
    norm_text = _ocr_normalize(text)
    for raw in keywords:
        kw = raw.strip()
        if kw and _ocr_normalize(kw) in norm_text:
            return True, kw
    return False, ""


def contains_any_keyword(text: str, keywords: Iterable[str]) -> Tuple[bool, str]:
    """Return (True, first_matched) if ``text`` contains any of ``keywords``.

    Used as a "must NOT contain" gate: when at least one exclude keyword
    hits, the scheduler skips the click chain for this round. Empty
    keyword list or empty text is treated as "no exclusion hit", so the
    caller can leave ``exclude_keywords`` unset without behavior change.

    Matching is tolerant of the single 己/已 confusables pair so a
    configured keyword like "自己的厂房" still triggers when OCR
    returns the visually-identical "自已的厂房".
    """
    if not text or not keywords:
        return False, ""
    norm_text = _ocr_normalize(text)
    for raw in keywords:
        kw = raw.strip()
        if kw and _ocr_normalize(kw) in norm_text:
            return True, kw
    return False, ""
