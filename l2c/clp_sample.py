"""Extract the manually associated L-13 footing schedule example locally.

This is a specific validation sample, not a general automatic association engine.
Values and coordinates come from native PDF text; the type/location association
is supplied by the user's visual confirmation, not inferred by ML.
"""
import argparse
import json
import re
from pathlib import Path

import pdfplumber
from l2c.annex_a import Annotation, Armature

BAR = re.compile(r"^(\d+)-((?:10|15|20|25|30|35|45|55)M)$")


def schedule_row(page, type_code):
    words = page.extract_words()
    possibilities = []
    for word in words:
        if word["text"].upper() not in ("TYPE", f"TYPE {type_code}"):
            continue
        labels = [w for w in words if w["text"].upper() == type_code and
                  abs(w["top"] - word["top"]) < 3 and
                  0 <= w["x0"] - word["x1"] < 30]
        if not labels and word["text"].upper() != f"TYPE {type_code}":
            continue
        bars = sorted([w for w in words if BAR.fullmatch(w["text"].upper()) and
                       abs(w["top"] - word["top"]) < 3 and w["x0"] > word["x1"]],
                      key=lambda w: w["x0"])
        if len(bars) == 2:
            possibilities.append((word, bars))
    if len(possibilities) != 1:
        raise ValueError(f"Expected one unambiguous schedule row for type {type_code}; found {len(possibilities)}")
    return possibilities[0], words


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True, help="Local CLP directory")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[1]) or any("onedrive" in p.lower() for p in output.parts):
        parser.error("Save confidential results outside the repo and OneDrive.")
    records, evidence = [], []
    specs = [("plan", "L2C_PLAN_STR_CLP.pdf", 4, "C"),
             ("atelier", "DA/Fondations/CLP_SEMELLES FND.pdf", 1, "B")]
    for source, filename, number, type_code in specs:
        with pdfplumber.open(args.data_dir / filename) as document:
            page = document.pages[number - 1]
            (anchor, bars), words = schedule_row(page, type_code)
            origin_x, origin_y = page.bbox[:2]
            sheets = sorted(set(w["text"] for w in words if re.fullmatch(r"S-\d{3}", w["text"]) and
                                w["x0"] - origin_x > page.width * 0.75 and
                                w["top"] - origin_y > page.height * 0.65))
            # The shop drawing can use a different numbering system. Preserve a
            # transparent file/page reference rather than invent an S-series ID.
            sheet = sheets[0] if len(sheets) == 1 else f"{Path(filename).stem} / page {number}"
            sheet_method = "title-block native text" if len(sheets) == 1 else "file/page fallback; title-block code unresolved"
            for direction, word in zip(("longitudinale", "transversale"), bars):
                quantity, diameter = BAR.fullmatch(word["text"].upper()).groups()
                record = Annotation(id=f"CLP_L13_{source}_{direction}",
                                    source=source, fichier=Path(filename).name, feuillet=sheet,
                                    page=number, x=(word["x0"]+word["x1"])/2-origin_x,
                                    y=(word["top"]+word["bottom"])/2-origin_y,
                                    type_element="semelle", element="L-13",
                                    armature=[Armature(diametre=diameter, quantite=int(quantity))])
                if not (record.x <= page.width and record.y <= page.height):
                    raise ValueError("Annotation centre outside displayed PDF page.")
                records.append(record.model_dump())
                evidence.append({"record_id": record.id, "direction": direction,
                                 "footing_type": type_code, "relative_file": filename,
                                 "annotation_box_points": [word["x0"]-origin_x,word["top"]-origin_y,
                                                           word["x1"]-origin_x,word["bottom"]-origin_y],
                                 "page_rotation": page.rotation,
                                 "sheet_identification_method": sheet_method,
                                 "pdfplumber_bbox_origin": [origin_x, origin_y],
                                 "page_size_points": [page.width,page.height],
                                 "association_method": "user-confirmed L-13 marker to footing schedule row",
                                 "extraction_method": "native PDF text and geometry; not ML",
                                 "unavailable_fields": ["repere", "espacement_mm", "longueur_mm"]})
    output.mkdir(parents=True, exist_ok=True)
    (output / "annex-a.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "association-evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"validated_records": len(records), "evidence_records": len(evidence),
                      "association": "manually confirmed", "extraction": "native PDF"}))


if __name__ == "__main__":
    main()
