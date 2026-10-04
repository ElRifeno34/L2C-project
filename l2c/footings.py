"""Conservative vector footing markers -> paired grid axes -> schedule rows."""
import re
from collections import defaultdict
from l2c.geometry import closed_outlines


def contains(box, x, y):
    return box.x0 <= x <= box.x1 and box.y0 <= y <= box.y1


def footing_context(page, words, annotations, drawings=None, outlines=None):
    """Only explicit paired axis bubbles and closed footing frames qualify.

    No nearest grid guessing and no project/location/expected-value constants.
    Schedule definitions remain unresolved if the geometry is insufficient.
    """
    if not any('SEMELLE' in w['text'].upper() for w in words):
        return [], {}
    if drawings is None:
        drawings = page.get_drawings()
    if outlines is None:
        outlines = closed_outlines(drawings, page.rotation_matrix)
    rectangles, bubbles, markers = [], [], []
    label_words = [w for w in words if re.fullmatch(r'[A-Z]{1,2}|\d{1,2}(?:\.\d+)?', w['text'])]
    shapes = [(o['bbox'], len(o['vertices']) >= 12, len(o['vertices']) == 6)
              for o in outlines if not o['rectangle']]
    rectangles = [o['bbox'] for o in outlines if o['rectangle']]
    for path in drawings:
        items = path['items']
        bezier_circle = len(items) in (4, 8) and all(i[0] == 'c' for i in items)
        poly_circle = (len(items) >= 12 and all(i[0] == 'l' for i in items)
                       and items[0][1].distance_to(items[-1][2]) < .15)
        if bezier_circle or poly_circle:
            shapes.append((path['rect'] * page.rotation_matrix, True, False))
    for box, circular, polygon in shapes:
        if not (4 <= box.width <= 45 and 4 <= box.height <= 45):
            continue
        circular = circular and .7 < box.width / box.height < 1.4
        if not (circular or polygon):
            continue
        labels = [w for w in label_words if contains(box, (w['x0'] + w['x1']) / 2,
                                               (w['top'] + w['bottom']) / 2)
                  ]
        if len(labels) != 1:
            continue
        item = (labels[0]['text'], (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2)
        (bubbles if circular else markers).append(item)
    axes = defaultdict(list)
    for label, x, y in bubbles:
        axes[label].append((x, y))
    vertical, horizontal = [], []
    for label, points in axes.items():
        for x, y in points:
            aligned_y = [p for p in points if abs(p[0] - x) < 3]
            aligned_x = [p for p in points if abs(p[1] - y) < 3]
            if len(aligned_y) >= 2 and max(p[1] for p in aligned_y) - min(p[1] for p in aligned_y) > page.rect.height * .2:
                vertical.append((label, x))
            if len(aligned_x) >= 2 and max(p[0] for p in aligned_x) - min(p[0] for p in aligned_x) > page.rect.width * .2:
                horizontal.append((label, y))
    vertical = list(set(vertical));horizontal = list(set(horizontal))
    instances = []
    for code, mx, my in markers:
        if not re.fullmatch('[A-G]', code):
            continue
        frames = [b for b in rectangles if contains(b, mx, my) and
                  20 < b.width < 300 and 20 < b.height < 300]
        if not frames:
            continue
        frame = min(frames, key=lambda b: b.width * b.height)
        cx, cy = (frame.x0 + frame.x1) / 2, (frame.y0 + frame.y1) / 2
        vs = {name for name, x in vertical if abs(x - cx) < frame.width * .2}
        hs = {name for name, y in horizontal if abs(y - cy) < frame.height * .2}
        if len(vs) == len(hs) == 1:
            labels = [next(iter(vs)), next(iter(hs))]
            letters = [n for n in labels if n.isalpha()]
            numbers = [n for n in labels if re.fullmatch(r'\d{1,2}(?:\.\d+)?', n)]
            if len(letters) != 1 or len(numbers) != 1:
                continue
            instances.append({'element': f'{letters[0]}-{numbers[0]}',
                              'type_element': 'semelle', 'footing_type': code})
    rows = {}
    for w in words:
        if w['text'].upper() != 'TYPE':
            continue
        codes = [c for c in words if re.fullmatch('[A-G]', c['text']) and
                 abs(c['top'] - w['top']) < 4 and 0 <= c['x0'] - w['x1'] < 35]
        if len(codes) != 1:
            continue
        code = codes[0]['text']
        tables = [b for b in rectangles if contains(b, w['x0'], w['top'])
                  and b.width > 200 and b.height > 50]
        table = min(tables, key=lambda b: b.width * b.height) if tables else page.rect
        bars = [a for a in annotations if abs(a['y'] - (w['top'] + w['bottom']) / 2) < 5
                and a['x'] > codes[0]['x1'] and contains(table, a['x'], a['y'])]
        if len(bars) == 2 and code not in rows:
            rows[code] = sorted(bars, key=lambda a: a['x'])
            for a in bars:
                headers = [h for h in words if 0 < w['top'] - h['top'] < 150
                           and abs((h['x0'] + h['x1']) / 2 - a['x']) < 40
                           and ('LONG' in h['text'].upper() or 'TRANS' in h['text'].upper())]
                if headers:
                    h = min(headers, key=lambda h: abs((h['x0'] + h['x1']) / 2 - a['x']))
                    a['direction'] = 'transversale' if 'TRANS' in h['text'].upper() else 'longitudinale'
    linked, annotation_context = [], {}
    for instance in instances:
        bars = rows.get(instance['footing_type'])
        if not bars:
            continue
        reference = f'footing-schedule:{bars[0]["fichier"]}:{bars[0]["page"]}:{instance["footing_type"]}'
        element = {k: bars[0][k] for k in ('source', 'fichier', 'feuillet', 'page')}
        element.update(element=instance['element'], type_element='semelle', schedule_ref=reference)
        if any(e['element'] == element['element'] for e in linked):
            continue
        linked.append(element)
        for a in bars:
            a['schedule_ref'] = reference
            a['context_provenance'] = 'closed footing marker + paired grid axis bubbles + explicit schedule type row'
            annotation_context[a['id']] = {'association_method': a['context_provenance']}
    return linked, annotation_context
