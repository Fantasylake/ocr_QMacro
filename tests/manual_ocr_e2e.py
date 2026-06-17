"""Quick end-to-end smoke test for the OCR backend swap.

Not part of pytest (we don't want to require both backends installed
to run the unit suite). Run with:
    python tests/manual_ocr_e2e.py
"""
import time
from core.ocr import recognize_text, backend_name, engine_init_ms
from core.matcher import normalize_text, texts_equal


def main() -> int:
    print(f"backend: {backend_name()}")

    with open("tests/fixtures/ocr_sample.png", "rb") as f:
        png = f.read()
    with open("tests/fixtures/ocr_simple.png", "rb") as f:
        png2 = f.read()

    # Round 1: baseline
    t0 = time.perf_counter()
    text1 = recognize_text(png)
    print(f"round 1 (baseline): {(time.perf_counter() - t0) * 1000:.0f}ms "
          f"init_so_far={engine_init_ms():.0f}ms")
    print(f"  raw: {text1!r}")
    base_norm = normalize_text(text1)
    print(f"  normalized: {base_norm!r}")

    # Round 2: same image -> must equal baseline
    t0 = time.perf_counter()
    text2 = recognize_text(png)
    print(f"round 2 (same image): {(time.perf_counter() - t0) * 1000:.0f}ms "
          f"texts_equal={texts_equal(text1, text2)}")

    # Round 3: different image
    t0 = time.perf_counter()
    text3 = recognize_text(png2)
    print(f"round 3 (different): {(time.perf_counter() - t0) * 1000:.0f}ms "
          f"texts_equal_vs_baseline={texts_equal(text1, text3)}")

    # Keyword spot-checks
    has_ok = "成功" in text1
    has_done = "完成" in text3
    print(f"  has 成功 in round 1: {has_ok}")
    print(f"  has 完成 in round 3: {has_done}")

    return 0 if (has_ok and has_done and texts_equal(text1, text2)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
