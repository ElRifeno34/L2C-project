"""Recover closed CAD outlines even when one PDF path contains several shapes."""
from collections import defaultdict

import pymupdf as fitz


def closed_outlines(drawings, matrix):
    """Independent degree-two cycles; open/branching linework is excluded.

    CAD exporters split or combine strokes independently of physical shapes.
    Joining endpoints at 0.1 PDF point recovers cycles without proximity guesses.
    """
    graph = defaultdict(set)
    points = {}
    for path in drawings:
        items = list(path['items'])
        if (path.get('closePath') and items and all(i[0] == 'l' for i in items)
                and all(a[2].distance_to(b[1]) < .15 for a, b in zip(items, items[1:]))):
            items.append(('l', items[-1][2], items[0][1]))
        for item in items:
            if item[0] == 'l':
                edges = [(item[1], item[2])]
            elif item[0] == 're':
                r = item[1]
                edges = [(r.tl, r.tr), (r.tr, r.br), (r.br, r.bl), (r.bl, r.tl)]
            else:
                continue
            for start, end in edges:
                start, end = start * matrix, end * matrix
                a, b = (round(start.x, 1), round(start.y, 1)), (round(end.x, 1), round(end.y, 1))
                if a == b:
                    continue
                points[a], points[b] = start, end
                graph[a].add(b)
                graph[b].add(a)
    visited = set()
    outlines = []
    for root in graph:
        if root in visited:
            continue
        pending, component = [root], set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(graph[current] - component)
        visited.update(component)
        if not 4 <= len(component) <= 100 or any(len(graph[v]) != 2 for v in component):
            continue
        cycle, previous, current = [], None, root
        while current not in cycle:
            cycle.append(current)
            following = next(v for v in graph[current] if v != previous)
            previous, current = current, following
        if current != root or len(cycle) != len(component):
            continue
        # Remove collinear split points before classifying rectangle/hexagon.
        vertices = [points[v] for v in cycle]
        simplified = []
        for index, middle in enumerate(vertices):
            before, after = vertices[index-1], vertices[(index+1) % len(vertices)]
            cross = abs((middle.x-before.x)*(after.y-middle.y) -
                        (middle.y-before.y)*(after.x-middle.x))
            length = before.distance_to(middle) + middle.distance_to(after)
            if cross > .05 * max(1, length):
                simplified.append(middle)
        if len(simplified) < 4:
            continue
        box = fitz.Rect(min(v.x for v in simplified), min(v.y for v in simplified),
                        max(v.x for v in simplified), max(v.y for v in simplified))
        rectangle = len(simplified) == 4 and all(
            abs(a.x-b.x) < .15 or abs(a.y-b.y) < .15
            for a, b in zip(simplified, simplified[1:]+simplified[:1]))
        outlines.append({'bbox': box, 'vertices': simplified, 'rectangle': rectangle})
    return outlines
