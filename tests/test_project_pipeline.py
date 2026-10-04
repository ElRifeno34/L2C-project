"""End-to-end PDF tests with synthetic drawings, not duplicated implementation."""
import tempfile
import unittest
from pathlib import Path

import pymupdf as fitz
from pypdf import PdfReader

from l2c.annex_a import Annotation
from l2c.pipeline import run_project
from l2c.rebar import element_labels, parse_callouts


class RebarParserTests(unittest.TestCase):
    def test_quantity_and_imperial_spacing(self):
        bar = parse_callouts('8-25M@11"')[0]['armature'][0]
        self.assertEqual(bar['quantite'], 8)
        self.assertAlmostEqual(bar['espacement_mm'], 279.4)

    def test_explicit_length_and_unknown_spacing_unit(self):
        bar = parse_callouts('25M@200 L=3.6M')[0]['armature'][0]
        self.assertIsNone(bar['espacement_mm'])
        self.assertEqual(bar['longueur_mm'], 3600)

    def test_lengths_are_not_reinforcement_and_sheets_are_not_slabs(self):
        self.assertEqual(parse_callouts('250MM et 125MM'), [])
        self.assertEqual(element_labels('S-500'), {})


class ProjectPipelineTests(unittest.TestCase):
    def draw(self, path, quantity, rotate=False, identifier=True):
        doc = fitz.open();page = doc.new_page(width=600, height=800)
        page.insert_text((80, 100), f"{'C-12 ' if identifier else ''}{quantity}-25M")
        page.insert_text((480, 740), 'S-500')
        if rotate: page.set_rotation(90)
        doc.save(path);doc.close()

    def test_real_pdf_input_produces_valid_json_and_discrepancy_pdf(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'example';(project/'DA').mkdir(parents=True)
            self.draw(project/'L2C_PLAN_STR_example.pdf',8)
            self.draw(project/'DA/shop.pdf',6)
            summary=run_project(project,root/'output')
            self.assertEqual(summary['processed_pages'],2)
            self.assertEqual(summary['record_count'],2)
            self.assertEqual(summary['errors'],[])
            records=json.loads((root/'output/annex-a.json').read_text())
            for r in records: Annotation.model_validate(r)
            result=json.loads((root/'output/reconciliation.json').read_text())
            self.assertEqual(result['S-500']['non_conforme'],1)
            text=''.join(p.extract_text() for p in PdfReader(root/'output/report.pdf').pages)
            self.assertIn('quantity: plan = 8 vs shop = 6',text)

    def test_unlabelled_reinforcement_is_unresolved_not_invented(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'example';project.mkdir()
            self.draw(project/'L2C_PLAN_STR_example.pdf',8,identifier=False)
            summary=run_project(project,root/'output')
            self.assertEqual(summary['record_count'],0)
            self.assertEqual(summary['unresolved_annotations'],1)

    def test_rotated_annotation_centres_use_displayed_page_points(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'example';project.mkdir()
            self.draw(project/'L2C_PLAN_STR_example.pdf',8,rotate=True)
            summary=run_project(project,root/'output')
            records=json.loads((root/'output/annex-a.json').read_text())
            self.assertEqual(summary['record_count'],1)
            with fitz.open(project/'L2C_PLAN_STR_example.pdf') as doc:
                word=next(w for w in doc[0].get_text('words') if w[4]=='8-25M')
                box=fitz.Rect(*word[:4])*doc[0].rotation_matrix
                self.assertAlmostEqual(records[0]['x'],(box.x0+box.x1)/2)
                self.assertAlmostEqual(records[0]['y'],(box.y0+box.y1)/2)

    def test_named_detail_frame_association(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'example';project.mkdir()
            doc=fitz.open();p=doc.new_page(width=600,height=800)
            p.draw_rect(fitz.Rect(50,50,500,600))
            p.insert_text((80,100),'P-12')
            p.insert_text((350,500),'8-25M')
            doc.save(project/'L2C_PLAN_STR_example.pdf');doc.close()
            summary=run_project(project,root/'output')
            self.assertEqual(summary['record_count'],1)
            self.assertEqual(summary['unresolved_annotations'],0)

    def test_vector_footing_marker_and_grid_links_to_schedule(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'example';project.mkdir()
            doc=fitz.open();p=doc.new_page(width=600,height=800)
            for text,x,y in [('13',300,60),('13',300,740),('L',60,300),('L',540,300)]:
                p.draw_circle(fitz.Point(x,y),10)
                p.insert_text((x-5,y+3),text,fontsize=9)
            p.draw_rect(fitz.Rect(250,250,350,350))
            p.draw_polyline([fitz.Point(x,y) for x,y in [(321,322),(336,322),(342,332),(336,342),(321,342),(315,332)]],closePath=True)
            p.insert_text((324,335),'C',fontsize=9)
            p.draw_rect(fitz.Rect(40,620,550,710))
            p.insert_text((60,640),'NOMENCLATURE DES SEMELLES')
            p.insert_text((60,670),'TYPE C')
            p.insert_text((310,670),'9-25M')
            p.insert_text((430,670),'9-25M')
            doc.save(project/'L2C_PLAN_STR_example.pdf');doc.close()
            summary=run_project(project,root/'output')
            self.assertEqual(summary['record_count'],2)


if __name__ == '__main__':
    unittest.main()
