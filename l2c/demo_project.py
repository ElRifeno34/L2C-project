"""Reproducible five-type synthetic PDF demo; contains no challenge documents."""
import argparse
import json
from pathlib import Path

import pymupdf as fitz

from l2c.pipeline import run_project, safe_output


CASES = [
    ('S-100', 'F-12', '9-25M', '11-25M'),
    ('S-300', 'P-12', '6-20M L=3000MM', '6-25M L=3000MM'),
    ('S-400', 'M-12', '15M@200MM', '15M@150MM'),
    ('S-500', 'C-12', '8-25M L=3600MM', '8-25M L=3300MM'),
    ('S-600', 'D-12', '10M@150MM', '10M@150MM'),
]


def make_demo_project(project_dir):
    project = safe_output(project_dir)
    (project / 'DA').mkdir(exist_ok=True)
    for source in ('plan', 'atelier'):
        doc = fitz.open()
        for sheet, element, plan, shop in CASES:
            page = doc.new_page(width=600, height=800)
            page.insert_text((60, 45), 'SYNTHETIC DEMO - no real project data', fontsize=12)
            page.draw_rect(fitz.Rect(60, 70, 530, 550))
            page.insert_text((80, 100), element, fontsize=14)
            page.insert_text((180, 250), plan if source == 'plan' else shop, fontsize=12)
            page.insert_textbox(fitz.Rect(60, 565, 535, 615),
                'This synthetic sheet illustrates an identified structural element and its reinforcement '
                'annotation. It validates the local pipeline; it does not establish performance on '
                'real construction documents.', fontsize=10)
            page.insert_text((480, 740), sheet if source == 'plan' else 'S-900')
            if sheet == 'S-600' and source == 'plan':
                page.insert_text((80, 620), '4-15M')  # unresolved, outside the named frame
        filename = project / ('L2C_PLAN_STR_demo.pdf' if source == 'plan' else 'DA/demo_shop.pdf')
        doc.save(filename)
        doc.close()
    return project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    project = make_demo_project(args.project_dir)
    summary = run_project(project, args.output_dir)
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == '__main__':
    main()
