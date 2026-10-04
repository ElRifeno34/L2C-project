"""Prepare local crops around native bar annotations for an OCR smoke benchmark."""
import argparse
import json
import re
from pathlib import Path

import pdfplumber
import pypdfium2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", type=int, required=True, help="One-based page number")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, default=3)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    if root.is_relative_to(Path(__file__).resolve().parents[1]) or any('onedrive' in p.lower() for p in root.parts):
        parser.error("Store confidential samples outside the repository.")
    root.mkdir(parents=True, exist_ok=True)
    samples = []
    with pdfplumber.open(args.pdf) as pdf:
        if not 1 <= args.page <= len(pdf.pages):
            parser.error("Page is outside the document.")
        page = pdf.pages[args.page - 1]
        words = page.extract_words()
        origin_x, origin_y = page.bbox[:2]
        for word in words:
            word["x0"] -= origin_x
            word["x1"] -= origin_x
            word["top"] -= origin_y
            word["bottom"] -= origin_y
        with pypdfium2.PdfDocument(args.pdf) as document:
            rendered_page = document[args.page - 1]
            bitmap = rendered_page.render(scale=2)
            image = bitmap.to_pil()
            for word in words:
                if len(samples) >= args.count:
                    break
                if not re.search(r"\d+M\b", word["text"], re.I):
                    continue
                box = [max(0, word["x0"] - 60), max(0, word["top"] - 45),
                       min(page.width, word["x1"] + 120),
                       min(page.height, word["bottom"] + 65)]
                if any(abs(box[0] - s["box"][0]) < 140 and
                       abs(box[1] - s["box"][1]) < 100 for s in samples):
                    continue
                target = root / f"crop-{len(samples)+1}.png"
                image.crop(tuple(int(v * 2) for v in box)).save(target)
                native = [w["text"] for w in words if box[0] <= w["x0"] and
                          w["x1"] <= box[2] and box[1] <= w["top"] and
                          w["bottom"] <= box[3]]
                samples.append({"file": str(target), "page": args.page,
                                "box": box, "native_text": native,
                                "render_scale": 2,
                                "crop_origin_pixels": [int(box[0]*2), int(box[1]*2)],
                                "page_size_points": [page.width, page.height],
                                "coordinate_system": "displayed PDF page, upper-left origin, points"})
            image.close()
            bitmap.close()
            rendered_page.close()
    (root / "samples.json").write_text(json.dumps(samples, indent=2), encoding="utf-8")
    print(f"Prepared {len(samples)} crops locally; no drawing content printed.")


if __name__ == "__main__":
    main()
