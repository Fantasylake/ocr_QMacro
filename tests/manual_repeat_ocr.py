"""Run recognize_text on the given PNG three times and print each result.

The same image is run three times back-to-back so we can compare
intra-process stability (the baseline-OCR invariant: same image must
produce texts_equal output across passes).
"""
import sys
import time
from pathlib import Path

from core.ocr import recognize_text, backend_name, engine_init_ms


def main() -> int:
    print(f"backend: {backend_name()}")
    print(f"engine init ms (so far): {engine_init_ms():.0f}")

    png_path = Path(sys.argv[1] if len(sys.argv) > 1 else
                    "src/pic/20260617/185508_a1_1.png")
    png = png_path.read_bytes()
    print(f"image: {png_path}  size={len(png)} bytes")

    results = []
    for i in range(1, 4):
        t0 = time.perf_counter()
        text = recognize_text(png)
        dt = (time.perf_counter() - t0) * 1000
        results.append(text)
        print(f"\n=== pass {i} ({dt:.0f}ms) ===")
        print(text)
        print(f"=== end pass {i} (len={len(text)}) ===")

    a, b, c = results
    print(f"\n--- comparison ---")
    print(f"pass 1 == pass 2: {a == b}")
    print(f"pass 2 == pass 3: {b == c}")
    print(f"all three equal: {a == b == c}")

    # Also check texts_equal (whitespace-tolerant)
    from core.matcher import texts_equal
    print(f"texts_equal(1,2): {texts_equal(a, b)}")
    print(f"texts_equal(2,3): {texts_equal(b, c)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
