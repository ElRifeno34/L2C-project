"""Local PDF project -> Annex A JSON, association evidence and per-sheet PDF."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import pymupdf as fitz

from l2c.annex_a import Annotation
from l2c.associate import associate_annotations
from l2c.extract import (apply_context, extract_annotations, identify_sheet,
                         framed_element_regions, associate_frames)
from l2c.rebar import parse_callouts
from src.match import match_and_reconcile
from src.report_pdf import generate_pdf_report


def safe_output(path):
    target = Path(path).resolve()
    repo = Path(__file__).resolve().parents[1]
    if target.is_relative_to(repo) or any('onedrive' in p.lower() for p in target.parts):
        raise ValueError('Store confidential results outside Git and OneDrive.')
    target.mkdir(parents=True, exist_ok=True)
    return target


def native_words(page):
    words = []
    for x0, y0, x1, y1, text, block, line, order in page.get_text('words', sort=True):
        box = fitz.Rect(x0, y0, x1, y1) * page.rotation_matrix
        word = {'text': text, 'x0': box.x0, 'x1': box.x1,
                'top': box.y0, 'bottom': box.y1}
        if page.rotation:
            word.update(native_line=(block, line), inline_x=x0, inline_right=x1, inline_height=y1-y0)
        words.append(word)
    return words


def render(page, box, scale=2):
    from PIL import Image
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=fitz.Rect(box), alpha=False)
    image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    return image, (pix.x / scale, pix.y / scale)


def source_for(path, project):
    relative = path.relative_to(project)
    if path.name.upper().startswith('L2C_PLAN_STR'):
        return 'plan'
    if any(p.upper() in ('DA', 'DESSINS ATELIER', 'DESSINS_ATELIER') for p in relative.parts[:-1]):
        return 'atelier'
    return None


def run_project(project_dir, output_dir, ocr='off', models_dir=None,
                context_file=None, max_pages=None, verify_crops=3, progress=None):
    """General conservative baseline. Unresolved annotations are never invented elements."""
    started = time.perf_counter()
    project = Path(project_dir).resolve()
    if not project.is_dir():
        raise ValueError('Project PDF directory not found.')
    target = safe_output(output_dir)
    context = json.loads(Path(context_file).read_text(encoding='utf8')) if context_file else []
    if isinstance(context, dict):
        context = context['regions']
    if ocr not in ('off', 'auto', 'hybrid'):
        raise ValueError('Unknown OCR mode.')
    model = None
    def get_model():
        nonlocal model
        if model is None:
            if not models_dir:
                raise ValueError('OCR requires --models-dir with preloaded local weights.')
            from l2c.local_ocr import LocalPaddle
            model = LocalPaddle(models_dir, target / 'runtime')
        return model
    records, associations, all_annotations, coverage, errors = [], [], [], [], []
    contexts, seen_ids = {}, set()
    verified = processed = 0
    sheets = set()
    unknown_files = []
    files = sorted(project.rglob('*.pdf'))
    for path in files:
        source = source_for(path, project)
        filename = path.relative_to(project).as_posix()
        if source is None:
            unknown_files.append(filename)
            continue
        try:
            document = fitz.open(path)
        except Exception as exc:
            errors.append({'fichier': filename, 'error': type(exc).__name__})
            continue
        with document:
            for page_index, page in enumerate(document):
                if max_pages is not None and processed >= max_pages:
                    break
                processed += 1
                try:
                    words = native_words(page)
                    method = 'native'
                    if len(words) < 20 and ocr != 'off':
                        # OCR at readable scale in overlapping tiles, never shrink a large sheet.
                        words = []
                        tile, step = 650, 600
                        for y in range(0, int(page.rect.height), step):
                            for x in range(0, int(page.rect.width), step):
                                box = (x, y, min(x + tile, page.rect.width), min(y + tile, page.rect.height))
                                image, origin = render(page, box)
                                words.extend(get_model().words(image, origin))
                                image.close()
                        method = 'paddle'
                    sheet, sheet_method = identify_sheet(words, filename, page_index + 1,
                                                         page.rect.width, page.rect.height)
                    if source == 'plan':
                        sheets.add(sheet)
                    annotations, elements = extract_annotations(words, source, filename, sheet,
                                                                page_index + 1, method)
                    annotations, elements = associate_frames(
                        annotations, elements, framed_element_regions(page, words))
                    annotations, elements = apply_context(annotations, elements, context,
                                                          page.rect.width, page.rect.height)
                    if ocr == 'hybrid' and method == 'native':
                        for annotation in annotations:
                            if verified >= verify_crops:
                                break
                            x0, y0, x1, y1 = annotation['bbox']
                            box = (max(0, x0 - 45), max(0, y0 - 30),
                                   min(page.rect.width, x1 + 45), min(page.rect.height, y1 + 30))
                            image, origin = render(page, box)
                            predicted = get_model().words(image, origin)
                            image.close()
                            parsed = [p['armature'][0] for w in predicted for p in parse_callouts(w['text'])]
                            expected = annotation['armature'][0]
                            agreement = any(p['diametre'] == expected['diametre'] and
                                            p['quantite'] == expected['quantite'] for p in parsed)
                            annotation['ml_verification'] = {'backend': 'PP-OCRv5_mobile', 'agreement': agreement}
                            verified += 1
                    result = associate_annotations(annotations, elements)
                    annotation_map = {a['id']: a for a in annotations}
                    for record in result['records']:
                        Annotation.model_validate(record)
                        if record['id'] in seen_ids:
                            continue
                        seen_ids.add(record['id'])
                        records.append(record)
                    for evidence in result['associations']:
                        a = annotation_map[evidence['annotation_id']]
                        evidence['fichier'], evidence['page'], evidence['feuillet'] = filename, page_index + 1, sheet
                        evidence['x'], evidence['y'] = a['x'], a['y']
                        evidence['ml_verification'] = a.get('ml_verification')
                        for record_id in evidence['record_ids']:
                            contexts[record_id] = {'instance_id': a.get('instance_id'),
                                                  'direction': a.get('direction'), 'review_reasons': []}
                            if a.get('ml_verification', {}).get('agreement') is False:
                                contexts[record_id]['review_reasons'].append('Native/OCR disagreement; verify source annotation')
                    all_annotations.extend(annotations)
                    associations.extend(result['associations'])
                    coverage.append({'source': source, 'fichier': filename, 'feuillet': sheet,
                                     'page': page_index + 1, 'width': page.rect.width,
                                     'height': page.rect.height, 'sheet_method': sheet_method,
                                     'text_method': method, 'annotation_count': len(annotations),
                                     'associated_count': sum(e['status'] == 'associated' for e in result['associations']),
                                     'unresolved_count': sum(e['status'] != 'associated' for e in result['associations'])})
                except Exception as exc:
                    errors.append({'fichier': filename, 'page': page_index + 1,
                                   'error': type(exc).__name__, 'message': str(exc)[:250]})
                if progress and processed % 10 == 0:
                    progress({'pages': processed, 'records': len(records), 'errors': len(errors)})
    reconciled = match_and_reconcile(records, contexts)
    for sheet in sheets:
        reconciled.setdefault(sheet, {'conforme': 0, 'non_conforme': 0, 'manquant': 0,
                                     'ajoute': 0, 'a_verifier': 0, 'discrepancies': []})
    reconciled = dict(sorted(reconciled.items()))
    # Absence cannot be proven when automatic association is incomplete.
    for stats in reconciled.values():
        for item in stats['discrepancies']:
            if item['status'] in ('MANQUANT', 'AJOUTÉ'):
                field = 'manquant' if item['status'] == 'MANQUANT' else 'ajoute'
                stats[field] -= 1
                stats['non_conforme'] -= 1
                stats['a_verifier'] += 1
                item['status'] = 'À VÉRIFIER'
                item['issues'].append('Automatic extraction has partial coverage; absence requires reviewer confirmation')
                item['detail'] = ' | '.join(item['issues'])
    summary = {'project': project.name, 'pdf_count': len(files), 'processed_pages': processed,
               'record_count': len(records), 'annotation_count': len(all_annotations),
               'associated_annotations': sum(e['status'] == 'associated' for e in associations),
               'unresolved_annotations': sum(e['status'] != 'associated' for e in associations),
               'ocr_verified_crops': verified, 'ocr_mode': ocr,
               'errors': errors, 'unclassified_files': unknown_files,
               'limited_run': max_pages is not None, 'seconds': round(time.perf_counter() - started, 3),
               'coverage_note': 'Prototype with partial automatic association. Zero detected discrepancies is not proof of conformity.',
               'outputs': ['annex-a.json', 'annotations.json', 'associations.json', 'coverage.json',
                           'reconciliation.json', 'run-summary.json', 'report.pdf']}
    for name, data in [('annex-a', records), ('annotations', all_annotations),
                       ('associations', associations), ('coverage', coverage),
                       ('reconciliation', reconciled), ('run-summary', summary)]:
        (target / f'{name}.json').write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf8')
    generate_pdf_report(reconciled, str(target / 'report.pdf'), coverage=coverage, associations=associations)
    if not coverage:
        raise ValueError('No PDF pages processed successfully; inspect run-summary.json.')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--ocr', choices=['off', 'auto', 'hybrid'], default='auto')
    parser.add_argument('--models-dir', type=Path)
    parser.add_argument('--context', type=Path, help='Local reviewer-supplied annotation regions JSON')
    parser.add_argument('--max-pages', type=int)
    parser.add_argument('--verify-crops', type=int, default=3)
    args = parser.parse_args()
    if args.max_pages is not None and args.max_pages < 1:
        parser.error('--max-pages must be positive')
    if args.ocr != 'off' and not args.models_dir:
        parser.error('--models-dir is required for offline OCR; use --ocr off for native-only extraction')
    summary = run_project(args.project_dir, args.output_dir, args.ocr, args.models_dir,
                          args.context, args.max_pages, args.verify_crops,
                          progress=lambda data: print(json.dumps(data), flush=True))
    print(json.dumps({k: v for k, v in summary.items() if k not in ('errors', 'unclassified_files')}, ensure_ascii=True))
    if summary['errors'] or summary['unclassified_files']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
