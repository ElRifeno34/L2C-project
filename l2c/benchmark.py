"""Benchmark local PDF text geometry. Never exports document text."""
import argparse
import json
import re
import time
from pathlib import Path

import pdfplumber


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error("Benchmark results must be stored outside the repository.")
    started = time.perf_counter()
    measurements = []
    with pdfplumber.open(args.pdf) as pdf:
        count = len(pdf.pages)
        indices = sorted({0, count // 2, count - 1})
        for index in indices:
            page = pdf.pages[index]
            tick = time.perf_counter()
            words = page.extract_words()
            elapsed = time.perf_counter() - tick
            # Candidate counts only; these are not validated reinforcement records.
            bar = re.compile(r"(?<!\d)\d+\s*M\b", re.I)
            number = re.compile(r"^\d+(?:[.,]\d+)?$")
            result = {
                "page": index + 1,
                "width_points": float(page.width),
                "height_points": float(page.height),
                "rotation": page.rotation,
                "word_count": len(words),
                "bar_designation_word_candidates": sum(bool(bar.search(w['text'])) for w in words),
                "numeric_word_candidates": sum(bool(number.fullmatch(w['text'])) for w in words),
                "words_with_valid_boxes": sum(0 <= w['x0'] <= w['x1'] <= page.width and
                                               0 <= w['top'] <= w['bottom'] <= page.height
                                               for w in words),
                "vector_lines": len(page.lines),
                "vector_curves": len(page.curves),
                "embedded_images": len(page.images),
                "text_geometry_seconds": round(elapsed, 3),
            }
            measurements.append(result)
            print(json.dumps(result), flush=True)
            page.close()
    report = {"page_count": count, "sample_strategy": "first, middle, last",
              "sample_pages": measurements,
              "elapsed_seconds": round(time.perf_counter() - started, 3),
              "ml_accuracy": None, "element_association_accuracy": None}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"page_count": count, "elapsed_seconds": report['elapsed_seconds']}))


if __name__ == "__main__":
    main()
