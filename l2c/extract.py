"""PDF reinforcement annotations with conservative, auditable associations."""
import hashlib
import re
from collections import defaultdict

from l2c.rebar import element_labels, parse_callouts


def text_segments(words):
    """Join aligned neighboring words, retaining offsets for annotation centres."""
    rows = []
    if words and all('native_line' in w for w in words):
        grouped = defaultdict(list)
        for w in words:
            grouped[w['native_line']].append(w)
        rows = list(grouped.values())
    for word in sorted(words, key=lambda w: (w['top'], w['x0'])):
        if 'native_line' in word:
            continue
        height = max(1, word['bottom'] - word['top'])
        row = next((r for r in reversed(rows[-20:])
                    if abs(r[0]['top'] - word['top']) < min(height * .5, 4)), None)
        if row is None:
            rows.append([word])
        else:
            row.append(word)
    for row in rows:
        parts = []
        for word in sorted(row, key=lambda w: w.get('inline_x', w['x0'])):
            if parts and word.get('inline_x', word['x0']) - parts[-1].get('inline_right', parts[-1]['x1']) > max(12, 2 * word.get('inline_height', word['bottom'] - word['top'])):
                yield segment(parts)
                parts = []
            parts.append(word)
        if parts:
            yield segment(parts)


def segment(words):
    text, offsets = '', []
    for word in words:
        if text:
            text += ' '
        start = len(text)
        text += word['text']
        offsets.append((start, len(text), word))
    return {'text': text, 'offsets': offsets}


def span_box(seg, start, end):
    words = [w for a, b, w in seg['offsets'] if a < end and b > start]
    return [min(w['x0'] for w in words), min(w['top'] for w in words),
            max(w['x1'] for w in words), max(w['bottom'] for w in words)]


def identify_sheet(words, filename, page, width, height):
    candidates = [w['text'].upper() for w in words
                  if re.fullmatch(r'S[- ]?\d{3}', w['text'], re.I)
                  and w['x0'] > width * .7 and w['top'] > height * .6]
    if len(set(candidates)) == 1:
        return candidates[0].replace(' ', '-'), 'title-block text'
    return f'{filename} / page {page}', 'file/page fallback; sheet code unresolved'


def extract_annotations(words, source, filename, sheet, page, method='native'):
    annotations, elements = [], {}
    for seg in text_segments(words):
        labels = element_labels(seg['text'])
        for name, kind in labels.items():
            key = name
            elements.setdefault(key, {'source': source, 'fichier': filename,
                                      'feuillet': sheet, 'page': page,
                                      'element': name, 'type_element': kind})
        for callout in parse_callouts(seg['text']):
            box = span_box(seg, callout['start'], callout['end'])
            ident = hashlib.sha256(f'{source}|{filename}|{page}|{box}|{callout["armature"]}'.encode()).hexdigest()[:20]
            entry = {'id': ident, 'source': source, 'fichier': filename, 'feuillet': sheet,
                     'page': page, 'x': (box[0] + box[2]) / 2,
                     'y': (box[1] + box[3]) / 2, 'bbox': box, 'armature': callout['armature'],
                     'context_provenance': f'{method}; same text segment identifiers',
                     'text': seg['text'], 'extraction_method': method}
            # Association is based on an identifier in the same annotation.
            if len(labels) == 1:
                entry['element_ref'] = next(iter(labels))
            annotations.append(entry)
    # Overlaid PDF text layers must not double count the same annotation.
    return list({a['id']: a for a in annotations}.values()), list(elements.values())


def apply_context(annotations, elements, context, width, height):
    """Optional reviewer regions. Context is an external local file, never GT."""
    for a in annotations:
        for item in context:
            if (item['source'], item['fichier'], item['page']) != (a['source'], a['fichier'], a['page']):
                continue
            region = item['bbox']
            if not (0 <= region[0] <= region[2] <= width and 0 <= region[1] <= region[3] <= height):
                raise ValueError('Context rectangle outside the displayed PDF page.')
            if region[0] <= a['x'] <= region[2] and region[1] <= a['y'] <= region[3]:
                a['element_ref'] = item['element']
                a['text'] = ''  # explicit reviewed region supersedes inferred text labels
                a['direction'] = item.get('direction')
                a['instance_id'] = item.get('instance_id')
                a['context_provenance'] = 'reviewer supplied region'
                element = {k: a[k] for k in ('source', 'fichier', 'feuillet', 'page')}
                element.update(element=item['element'], type_element=item['type_element'])
                if not any(e['element'] == element['element'] for e in elements):
                    elements.append(element)
    return annotations, elements


def framed_element_regions(page, words):
    """Named detail frames provide stronger context than nearest-label distance."""
    regions = []
    labelled_words = [(w, element_labels(w['text'])) for w in words]
    labelled_words = [(w, labels) for w, labels in labelled_words if labels]
    for path in page.get_drawings():
        items = path['items']
        if len(items) != 1 or items[0][0] != 're':
            continue
        box = items[0][1] * page.rotation_matrix
        if box.width < 70 or box.height < 35 or box.width > page.rect.width * .9 or box.height > page.rect.height * .9:
            continue
        labels = {}
        for w, found in labelled_words:
            if (box.x0 <= (w['x0'] + w['x1']) / 2 <= box.x1 and
                    box.y0 <= (w['top'] + w['bottom']) / 2 <= box.y1):
                labels.update(found)
        if len(labels) == 1:
            name, kind = next(iter(labels.items()))
            regions.append({'bbox': list(box), 'element': name, 'type_element': kind})
    return regions


def associate_frames(annotations, elements, regions):
    for a in annotations:
        matches = [r for r in regions if r['bbox'][0] <= a['x'] <= r['bbox'][2]
                   and r['bbox'][1] <= a['y'] <= r['bbox'][3]]
        labels = {r['element']: r['type_element'] for r in matches}
        if a.get('element_ref') or not labels:
            continue
        for name, kind in labels.items():
            e = {k: a[k] for k in ('source', 'fichier', 'feuillet', 'page')}
            e.update(element=name, type_element=kind)
            if not any(x['element'] == name for x in elements):
                elements.append(e)
        a['text'] = ' '.join(labels)
        a['context_provenance'] = 'element identifier inside enclosing detail frame'
        if len(labels) == 1:
            a['element_ref'] = next(iter(labels))
    return annotations, elements
