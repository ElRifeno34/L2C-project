import argparse
import json

from match import match_and_reconcile
from report_pdf import generate_pdf_report


def main():
    parser = argparse.ArgumentParser(
        description="Compare plan and shop drawing records and write a PDF report.")
    parser.add_argument("records_json", help="JSON file produced by the extraction step")
    parser.add_argument("--out", default="report.pdf", help="where to write the PDF report")
    args = parser.parse_args()

    with open(args.records_json, encoding="utf-8") as f:
        records = json.load(f)

    reconciled = match_and_reconcile(records)
    generate_pdf_report(reconciled, args.out)
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()