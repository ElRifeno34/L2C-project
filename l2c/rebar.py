"""Parse explicit Canadian reinforcement notation without inferring dimensions."""
import re

DIAMETER = r"(?:10|15|20|25|30|35|45|55)\s*M"
CALLOUT = re.compile(
    rf"(?<![\w.])(?:(?P<quantity>\d{{1,4}})\s*[-–]\s*)?"
    rf"(?P<diameter>{DIAMETER})(?![A-Z\d])", re.I)
SPACING = re.compile(r'^\s*(?:@|À|A\s+|C/C\s*)\s*(\d+(?:[.,]\d+)?)\s*(MM|CM|"|″|PO)?', re.I)
LENGTH = re.compile(r'\b(?:L|LONG(?:UEUR)?)\s*[:=]\s*(\d+(?:[.,]\d+)?)\s*(MM|CM|M)\b', re.I)
LABEL = re.compile(r'(?<![\w-])(?P<prefix>C|P|B|M|V|D|F|S)\s*-?\s*(?P<number>\d{1,3})(?P<suffix>[A-Z]?)(?![\w-])', re.I)
TYPES = {'C': 'colonne', 'P': 'poutre', 'B': 'poutre', 'M': 'mur',
         'V': 'mur', 'D': 'dalle', 'S': 'dalle', 'F': 'semelle'}


def metric(value, unit):
    return float(value.replace(',', '.')) * {'MM': 1, 'CM': 10, 'M': 1000,
                                              '"': 25.4, '″': 25.4, 'PO': 25.4}[unit.upper()]


def parse_callouts(text):
    """Return bar values plus character spans. Unspecified units stay unknown."""
    items = []
    matches = list(CALLOUT.finditer(text))
    for index, match in enumerate(matches):
        bar = {'repere': None, 'diametre': re.sub(r'\s+', '', match['diameter']).upper(),
               'quantite': int(match['quantity']) if match['quantity'] else None,
               'espacement_mm': None, 'longueur_mm': None}
        end = match.end()
        boundary = matches[index+1].start() if index+1 < len(matches) else len(text)
        following = text[end:boundary]
        spacing = SPACING.match(following)
        if spacing and spacing[2]:
            bar['espacement_mm'] = metric(spacing[1], spacing[2])
            end += spacing.end()
        length = LENGTH.search(following)
        if length:
            bar['longueur_mm'] = metric(length[1], length[2])
            end = max(end, match.end() + length.end())
        if any(bar[k] is not None and bar[k] <= 0 for k in ('espacement_mm', 'longueur_mm')):
            continue
        items.append({'armature': [bar], 'start': match.start(), 'end': end})
    return items


def element_labels(text):
    labels = {}
    for match in LABEL.finditer(text):
        # S-500 is a sheet number, not a slab identifier.
        if match['prefix'].upper() == 'S' and len(match['number']) == 3:
            continue
        name = f"{match['prefix'].upper()}-{match['number']}{match['suffix'].upper()}"
        labels[name] = TYPES[match['prefix'].upper()]
    return labels
