"""End-to-end PDF tests with synthetic drawings, not duplicated implementation."""
import tempfile
import unittest
from pathlib import Path

import pymupdf as fitz
from pypdf import PdfReader

from l2c.annex_a import Annotation
from l2c.pipeline import run_project
from l2c.rebar import element_labels, parse_callouts
from l2c.extract import apply_context, deduplicate_words
from l2c.geometry import closed_outlines
from l2c.pipeline import needs_ocr


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

    def test_length_never_crosses_into_next_reinforcement_callout(self):
        text = '8-25M 6-20M L=2000MM'
        bars = parse_callouts(text)
        self.assertIsNone(bars[0]['armature'][0]['longueur_mm'])
        self.assertEqual(bars[1]['armature'][0]['longueur_mm'], 2000)
        self.assertEqual(bars[1]['end'], len(text))

    def test_annex_coordinates_and_bar_values_must_be_finite(self):
        from pydantic import ValidationError
        from l2c.annex_a import Armature
        with self.assertRaises(ValidationError):
            Armature(longueur_mm=float('inf'))
        with self.assertRaises(ValidationError):
            Annotation(id='x',source='plan',fichier='a.pdf',feuillet='S-500',page=1,
                       x=float('nan'),y=10,type_element='colonne',element='C-12',armature=[{}])

    def test_blank_identity_cannot_become_a_comparable_element(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            Annotation(id='x',source='plan',fichier='a.pdf',feuillet='S-500',page=1,
                       x=10,y=10,type_element='colonne',element='   ',
                       armature=[{'diametre':'25M','quantite':8}])


class GeometryAndContextTests(unittest.TestCase):
    def test_composite_cad_path_recovers_independent_closed_outlines(self):
        doc=fitz.open();p=doc.new_page(width=600,height=800)
        shape=p.new_shape()
        shape.draw_rect(fitz.Rect(100,100,300,300))
        shape.draw_polyline([fitz.Point(x,y) for x,y in
                            [(240,240),(255,240),(262,250),(255,260),(240,260),(233,250),(240,240)]])
        shape.finish();shape.commit()
        outlines=closed_outlines(p.get_drawings(),p.rotation_matrix)
        self.assertEqual(sum(o['rectangle']for o in outlines),1)
        self.assertEqual(sum(len(o['vertices'])==6 for o in outlines),1)
        doc.close()

    def test_reviewed_region_supersedes_shared_schedule_and_inferred_type(self):
        annotation={'source':'plan','fichier':'a.pdf','feuillet':'S-100','page':1,
                    'x':110,'y':110,'schedule_ref':'table:C','text':'C-12'}
        elements=[{'source':'plan','fichier':'a.pdf','feuillet':'S-100','page':1,
                   'element':'L-13','type_element':'colonne'}]
        region={'source':'plan','fichier':'a.pdf','page':1,'bbox':[100,100,120,120],
                'element':'L-13','type_element':'semelle'}
        a,e=apply_context([annotation],elements,[region],600,800)
        self.assertNotIn('schedule_ref',a[0])
        self.assertEqual(e[0]['type_element'],'semelle')
        with self.assertRaises(ValueError):
            apply_context(a,e,[region,dict(region,element='L-14')],600,800)

    def test_overlapping_tile_words_do_not_duplicate_distinct_annotations(self):
        a={'text':'8-25M','x0':100,'x1':140,'top':100,'bottom':110}
        overlap=dict(a,x0=100.5,x1=140.5)
        neighbor=dict(a,x0=150,x1=190)
        self.assertEqual(len(deduplicate_words([a,overlap,neighbor])),2)

    def test_large_scan_with_vector_title_block_still_requests_ocr(self):
        import io
        from PIL import Image
        doc=fitz.open();p=doc.new_page(width=600,height=800)
        data=io.BytesIO();Image.new('RGB',(600,800),'white').save(data,format='PNG')
        p.insert_image(p.rect,stream=data.getvalue())
        words=[{'text':'title','x0':10,'x1':40,'top':10+i*10,'bottom':20+i*10}for i in range(25)]
        self.assertTrue(needs_ocr(p,words))
        doc.close()


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

    def test_five_types_end_to_end_detects_four_differences_and_one_conformity(self):
        import json
        from l2c.demo_project import make_demo_project
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            project=make_demo_project(root/'synthetic')
            summary=run_project(project,root/'output')
            records=json.loads((root/'output/annex-a.json').read_text())
            result=json.loads((root/'output/reconciliation.json').read_text())
            self.assertEqual({r['type_element']for r in records},
                             {'semelle','poutre','mur','colonne','dalle'})
            self.assertEqual(sum(s['non_conforme']for s in result.values()),4)
            self.assertEqual(sum(s['conforme']for s in result.values()),1)
            self.assertEqual(summary['unresolved_annotations'],1)
            self.assertEqual(summary['errors'],[])

    def test_unlabelled_reinforcement_is_unresolved_not_invented(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'example';project.mkdir()
            self.draw(project/'L2C_PLAN_STR_example.pdf',8,identifier=False)
            summary=run_project(project,root/'output')
            self.assertEqual(summary['record_count'],0)
            self.assertEqual(summary['unresolved_annotations'],1)

    def test_explicit_zero_ocr_budget_is_visible_in_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'example';project.mkdir()
            self.draw(project/'L2C_PLAN_STR_example.pdf',8)
            summary=run_project(project,root/'output',ocr='auto',max_ocr_pages=0)
            self.assertEqual(summary['ocr_processed_pages'],0)
            self.assertEqual(summary['ocr_skipped_pages'],1)
            self.assertEqual(summary['record_count'],1)

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
