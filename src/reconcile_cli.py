import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pydantic import TypeAdapter, ValidationError
from l2c.annex_a import Annotation

from match import match_and_reconcile
from report_pdf import generate_pdf_report


def main():
    parser = argparse.ArgumentParser(
        description="Compare plan and shop drawing records and write a PDF report.")
    parser.add_argument("records_json", help="JSON file produced by the extraction step")
    parser.add_argument("--out", required=True, help="local PDF output outside Git/cloud-synced folders")
    parser.add_argument("--mock-input", action="store_true",
                        help="Synthetic legacy fixtures only: bypass Annex A validation")
    args = parser.parse_args()

    output = Path(args.out).resolve()
    repo = Path(__file__).resolve().parents[1]
    if output.is_relative_to(repo) or any("onedrive" in p.lower() for p in output.parts):
        parser.error("Store reports outside Git and OneDrive.")
    with open(args.records_json, encoding="utf-8") as f:
        records = json.load(f)

    if not args.mock_input:
        try:
            records = [r.model_dump() for r in TypeAdapter(list[Annotation]).validate_python(records)]
        except ValidationError:
            parser.error("Input is not valid Annex A JSON; check fields, source, page, coordinates and armature.")

    reconciled = match_and_reconcile(records)
    output.parent.mkdir(parents=True, exist_ok=True)
    generate_pdf_report(reconciled, str(output))
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
