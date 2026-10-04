"""Within-document annotation association; no cross-document comparison.

Input boxes and points use displayed-page PDF points, upper-left origin.
Detected element regions/labels, leaders and schedule references are upstream
context. Proximity alone never confirms an association.
"""
import argparse
import json
import re
from pathlib import Path

from l2c.annex_a import Annotation


def page_key(item):
    return tuple(item[k] for k in ("source", "fichier", "feuillet", "page"))


def inside(point, box):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def associate_annotations(annotations, elements):
    """Return Annex A records and evidence. Abstain when evidence conflicts.

    An annotation may contain schedule_ref, element_ref or leader_endpoint.
    Elements contain element, type_element and optionally bbox/schedule_ref.
    Shared schedule annotations can intentionally link to several elements.
    Confidence is not assigned: no calibrated confidence model exists yet.
    """
    ids = [a["id"] for a in annotations]
    if len(ids) != len(set(ids)):
        raise ValueError("Annotation IDs must be unique.")
    identities = [(page_key(e), e["element"]) for e in elements]
    if len(identities) != len(set(identities)):
        raise ValueError("Element identifiers must be unique within a source page.")
    records, evidence = [], []
    for a in annotations:
        available = [e for e in elements if page_key(e) == page_key(a)]
        candidates = {}
        for index, e in enumerate(available):
            reasons = []
            if a.get("element_ref") == e["element"]:
                reasons.append("explicit_element_reference")
            if a.get("text") and re.search(r"(?<![\w-])" + re.escape(e["element"]) + r"(?![\w-])", a["text"]):
                reasons.append("element_identifier_in_annotation")
            if a.get("leader_endpoint") and e.get("bbox") and inside(a["leader_endpoint"], e["bbox"]):
                reasons.append("leader_endpoint_in_element_region")
            if e.get("bbox") and inside((a["x"], a["y"]), e["bbox"]):
                reasons.append("annotation_inside_element_region")
            if a.get("schedule_ref") and a["schedule_ref"] == e.get("schedule_ref"):
                reasons.append("marker_to_schedule_reference")
            if reasons:
                candidates[index] = reasons
        shared_schedule = bool(candidates) and all(
            reasons == ["marker_to_schedule_reference"] for reasons in candidates.values())
        accepted = len(candidates) == 1 or shared_schedule
        item = {"annotation_id": a["id"],
                "status": "associated" if accepted else "ambiguous" if candidates else "unresolved",
                "candidates": [{"element": available[i]["element"], "reasons": reasons}
                               for i, reasons in candidates.items()],
                "annotation_box_points": a.get("bbox"),
                "schedule_ref": a.get("schedule_ref"), "direction": a.get("direction"),
                "context_provenance": a.get("context_provenance", "unspecified"),
                "record_ids": []}
        if accepted:
            for index in candidates:
                e = available[index]
                record = Annotation.model_validate({
                    **{k: a[k] for k in ("source", "fichier", "feuillet", "page", "x", "y", "armature")},
                    "id": json.dumps([a["id"], e["element"]], ensure_ascii=False, separators=(",", ":")),
                    "type_element": e["type_element"], "element": e["element"]})
                records.append(record.model_dump())
                item["record_ids"].append(record.id)
        evidence.append(item)
    return {"records": records, "associations": evidence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    target = args.output_dir.resolve()
    if target.is_relative_to(Path(__file__).resolve().parents[1]) or any("onedrive" in part.lower() for part in target.parts):
        parser.error("Store confidential outputs outside Git and OneDrive.")
    data = json.loads(args.input.read_text(encoding="utf-8"))
    result = associate_annotations(data["annotations"], data["elements"])
    target.mkdir(parents=True, exist_ok=True)
    (target / "annex-a.json").write_text(json.dumps(result["records"], indent=2, ensure_ascii=False), encoding="utf-8")
    (target / "associations.json").write_text(json.dumps(result["associations"], indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"records": len(result["records"]),
                      **{s: sum(e["status"] == s for e in result["associations"])
                         for s in ("associated", "ambiguous", "unresolved")}}))


if __name__ == "__main__":
    main()
