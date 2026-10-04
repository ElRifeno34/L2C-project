"""
match.py - pair plan elements with shop-drawing elements and compare them.
 
Input : a list of JSON records following the Appendix A schema.
Output: a dict keyed by plan sheet, e.g.
 
    {
      "S-500": {
          "conforme": 12, "non_conforme": 3, "manquant": 1, "ajoute": 1,
          "discrepancies": [ {...}, {...} ]
      },
      ...
    }
 
Each entry in "discrepancies" has: feuillet, element, type, status, detail,
issues (list of short sentences), x, y, page, fichier, plan, shop.
"""
 
import re
from collections import Counter
import warnings
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple
 
# ---------------------------------------------------------------- settings --
 
# False: an element is identified by (type, name) only, because the plan and
#        the shop drawing may label their sheets differently.
# True : the sheet number is also part of the identity.
MATCH_ON_SHEET = False
 
# Differences up to these values are NOT reported (0 = must be identical).
LENGTH_TOLERANCE_MM = 0
SPACING_TOLERANCE_MM = 0
 
# Accepted values of the "source" field.
PLAN_SOURCES = {"plan"}
SHOP_SOURCES = {"shop_drawing", "shop", "atelier", "dessin_atelier"}
 
Key = Tuple[str, str, str]
 
 
# ----------------------------------------------------------- normalization --
 
def normalize_name(name: Optional[Any]) -> str:
    """'C - 12', 'c-12' and 'C12' all become 'C12' so trivial typing
    differences do not create fake mismatches."""
    if name is None:
        return ""
    return re.sub(r"[\s\-_]+", "", str(name)).upper()
 
 
def normalize_type(value: Optional[Any]) -> str:
    return str(value or "").strip().lower()
 
 
def build_key(item: Dict[str, Any]) -> Key:
    sheet = normalize_name(item.get("feuillet")) if MATCH_ON_SHEET else ""
    return (sheet, normalize_type(item.get("type_element")), normalize_name(item.get("element")))
 
 
def _to_number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
 
 
# ---------------------------------------------------------------- grouping --
 
def group_records(records: List[Dict[str, Any]]):
    """Sort records into 'plan' and 'shop' piles. Each pile maps a key to a
    LIST of records, so two records with the same key never overwrite each
    other."""
    plans: Dict[Key, List[Dict[str, Any]]] = defaultdict(list)
    shops: Dict[Key, List[Dict[str, Any]]] = defaultdict(list)
 
    for item in records:
        source = str(item.get("source", "")).strip().lower()
        if source in PLAN_SOURCES:
            plans[build_key(item)].append(item)
        elif source in SHOP_SOURCES:
            shops[build_key(item)].append(item)
        else:
            warnings.warn(f"Record {item.get('id')!r} skipped: unknown source {source!r}")
    return plans, shops
 
 
def merge_group(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Several records with the same key become one record whose bar list is
    the concatenation of all of them. Metadata comes from the first one."""
    ordered = sorted(
        records,
        key=lambda r: (r.get("page") or 0, r.get("y") or 0.0, r.get("x") or 0.0),
    )
    merged = dict(ordered[0])
    merged["armature"] = [bar for r in ordered for bar in (r.get("armature") or [])]
    return merged
 
 
# ------------------------------------------------------ bar-level checking --
 
def _fmt(values: List[Any]) -> str:
    return ", ".join(f"{v:g}" if isinstance(v, float) else str(v) for v in values)
 
 
def _total_quantity(bars: List[Dict[str, Any]]) -> List[float]:
    quantities = [_to_number(b.get("quantite")) for b in bars]
    if any(q is None for q in quantities):
        return []
    return [sum(quantities)] if quantities else []
 
 
def _diameters(bars: List[Dict[str, Any]]) -> List[str]:
    return sorted({normalize_name(b.get("diametre")) for b in bars if b.get("diametre")})
 
 
def _numbers(bars: List[Dict[str, Any]], field: str) -> List[float]:
    values = {_to_number(b.get(field)) for b in bars}
    return sorted(v for v in values if v is not None)
 
 
def _equal_exact(a: List[Any], b: List[Any]) -> bool:
    return a == b
 
 
def _numbers_close(tolerance: float) -> Callable[[List[float], List[float]], bool]:
    def check(a: List[float], b: List[float]) -> bool:
        return len(a) == len(b) and all(abs(x - y) <= tolerance for x, y in zip(a, b))
    return check
 
 
def _compare(label: str, plan_vals: List[Any], shop_vals: List[Any], equal) -> Optional[str]:
    """Describe a difference between known values. Missing values need review."""
    if not plan_vals and not shop_vals:
        return None
    if not plan_vals or not shop_vals:
        # Missing extraction evidence is recorded separately for review.
        return None
    if equal(plan_vals, shop_vals):
        return None
    return f"{label}: plan = {_fmt(plan_vals)} vs shop = {_fmt(shop_vals)}"
 
 
def _group_bars(armature: Optional[List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """Bars grouped by their mark ('repere'), e.g. 'C12-1'."""
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for bar in armature or []:
        groups[normalize_name(bar.get("repere"))].append(bar)
    return groups
 
 
def compare_armature(plan_bars, shop_bars) -> List[str]:
    plan_groups = _group_bars(plan_bars)
    shop_groups = _group_bars(shop_bars)
 
    if not plan_groups or not shop_groups:
        return []

    # Keep quantities attached to properties, including repeated marks.
    # A single property group still uses the detailed field comparison below.
    def signature(bar):
        return (normalize_name(bar.get("diametre")),
                _to_number(bar.get("espacement_mm")),
                _to_number(bar.get("longueur_mm")))
    grouped_issues = []
    for mark in sorted(set(plan_groups) & set(shop_groups)):
        left_bars, right_bars = plan_groups[mark], shop_groups[mark]
        signatures = {signature(b) for b in left_bars + right_bars}
        if len(signatures) <= 1:
            continue
        if len({signature(b) for b in left_bars}) == len({signature(b) for b in right_bars}) == 1:
            # Homogeneous groups have a direct attribute comparison, even if
            # they contain several split quantity rows.
            continue
        if any(_to_number(b.get("quantite")) is None or not b.get("diametre")
               for b in left_bars + right_bars):
            continue
        # A property missing on one side cannot establish a difference.
        if any(any(b.get(field) is None for b in left_bars) !=
               any(b.get(field) is None for b in right_bars)
               for field in ("espacement_mm", "longueur_mm")):
            continue
        def quantities(bars):
            totals = Counter()
            for bar in bars:
                totals[signature(bar)] += _to_number(bar.get("quantite")) or 0
            return totals
        left, right = quantities(left_bars), quantities(right_bars)
        for sig in sorted(signatures, key=repr):
            if left.get(sig) != right.get(sig):
                diameter, spacing, length = sig
                properties = [diameter]
                if spacing is not None:
                    properties.append(f"spacing {spacing:g} mm")
                if length is not None:
                    properties.append(f"length {length:g} mm")
                grouped_issues.append(
                    f"Bar {mark or '(no mark)'} [{'; '.join(properties)}]: quantity on plan = "
                    f"{left.get(sig, 'missing')} vs shop = {right.get(sig, 'missing')}")
        plan_groups.pop(mark)
        shop_groups.pop(mark)

    checks = [
        ("quantity", _total_quantity, _equal_exact),
        ("diameter", _diameters, _equal_exact),
        ("spacing (mm)", lambda bars: _numbers(bars, "espacement_mm"), _numbers_close(SPACING_TOLERANCE_MM)),
        ("length (mm)", lambda bars: _numbers(bars, "longueur_mm"), _numbers_close(LENGTH_TOLERANCE_MM)),
    ]
 
    issues: List[str] = list(grouped_issues)
    for mark in sorted(set(plan_groups) | set(shop_groups)):
        first_bar = (plan_groups.get(mark) or shop_groups.get(mark))[0]
        name = str(first_bar.get("repere") or "").strip() or "(no mark)"
        if mark not in shop_groups:
            issues.append(f"Bar {name}: on plan but missing from shop drawing")
            continue
        if mark not in plan_groups:
            issues.append(f"Bar {name}: on shop drawing but not on plan")
            continue
        for label, extract, equal in checks:
            problem = _compare(label, extract(plan_groups[mark]), extract(shop_groups[mark]), equal)
            if problem:
                issues.append(f"Bar {name} - {problem}")
    return issues


def reinforcement_review_reasons(plan_bars, shop_bars) -> List[str]:
    """Missing evidence cannot prove either conformity or non-conformity."""
    if not plan_bars or not shop_bars:
        return ["Insufficient reinforcement extraction on one or both sides"]
    reasons = []
    fields = ("diametre", "quantite", "espacement_mm", "longueur_mm")
    if any(all(b.get(f) is None for f in fields) for b in plan_bars + shop_bars):
        reasons.append("A reinforcement annotation has no comparable values")
    plans, shops = _group_bars(plan_bars), _group_bars(shop_bars)
    for mark in set(plans) & set(shops):
        left, right = plans[mark], shops[mark]
        for field in fields:
            missing_left = any(b.get(field) is None for b in left)
            missing_right = any(b.get(field) is None for b in right)
            if missing_left != missing_right:
                reasons.append(f"Bar {mark or '(no mark)'}: incomplete {field} extraction")
        if len(left) > 1 or len(right) > 1:
            if any(b.get("quantite") is None for b in left + right):
                reasons.append(f"Bar {mark or '(no mark)'}: unknown quantities prevent aggregation")
    return reasons
 
 
# ------------------------------------------------------------ result build --
 
def _location(record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if record is None:
        return None
    return {
        "fichier": record.get("fichier"),
        "page": record.get("page"),
        "x": record.get("x"),
        "y": record.get("y"),
    }
 
 
def _entry(plan, shop, status: str, issues: List[str]) -> Dict[str, Any]:
    ref = plan or shop
    return {
        "feuillet": ref.get("feuillet") or "UNKNOWN",
        "element": ref.get("element"),
        "type": ref.get("type_element"),
        "status": status,
        "issues": issues,
        "detail": " | ".join(issues),
        "x": ref.get("x") if ref.get("x") is not None else 0.0,
        "y": ref.get("y") if ref.get("y") is not None else 0.0,
        "page": ref.get("page"),
        "fichier": ref.get("fichier"),
        "plan": _location(plan),
        "shop": _location(shop),
    }
 
 
def _new_sheet_stats() -> Dict[str, Any]:
    return {"conforme": 0, "non_conforme": 0, "manquant": 0, "ajoute": 0, "a_verifier": 0, "discrepancies": []}
 
 
def match_and_reconcile(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    plans, shops = group_records(records)
    results: Dict[str, Dict[str, Any]] = defaultdict(_new_sheet_stats)
 
    for key in sorted(set(plans) | set(shops)):
        plan_records = plans.get(key, [])
        shop_records = shops.get(key, [])
        # Annex A has no shared level/instance identifier. Do not guess a
        # pairing when a name occurs in multiple document locations.
        def document_locations(items):
            return {(r.get("fichier"), r.get("feuillet"), r.get("page")) for r in items}
        if len(document_locations(plan_records)) > 1 or len(document_locations(shop_records)) > 1:
            review_records = plan_records or shop_records
            by_location = defaultdict(list)
            for record in review_records:
                by_location[(record.get("fichier"), record.get("feuillet"), record.get("page"))].append(record)
            for instance in by_location.values():
                ref = merge_group(instance)
                sheet = ref.get("feuillet") or "UNKNOWN"
                status = "À VÉRIFIER" if plan_records and shop_records else "MANQUANT" if plan_records else "AJOUTÉ"
                if status == "À VÉRIFIER":
                    results[sheet]["a_verifier"] += 1
                    reason = "Repeated element identifier across document locations; explicit instance association required"
                else:
                    results[sheet]["non_conforme"] += 1
                    results[sheet]["manquant" if plan_records else "ajoute"] += 1
                    reason = "Element missing from shop drawings" if plan_records else "Element added in shop drawings"
                results[sheet]["discrepancies"].append(_entry(
                    ref if plan_records else None, None if plan_records else ref,
                    status, [reason]))
            continue
        plan = merge_group(plan_records) if plan_records else None
        shop = merge_group(shop_records) if shop_records else None
 
        # Case 1: on the plan, not in the shop drawings
        if plan and not shop:
            sheet = plan.get("feuillet") or "UNKNOWN"
            results[sheet]["non_conforme"] += 1
            results[sheet]["manquant"] += 1
            results[sheet]["discrepancies"].append(_entry(
                plan, None, "MANQUANT",
                ["Element specified on the plan but missing from the shop drawings"]))
            continue
 
        # Case 2: in the shop drawings, not on the plan
        if shop and not plan:
            sheet = shop.get("feuillet") or "UNKNOWN"
            results[sheet]["non_conforme"] += 1
            results[sheet]["ajoute"] += 1
            results[sheet]["discrepancies"].append(_entry(
                None, shop, "AJOUTÉ",
                ["Element present in the shop drawings but not on the plan"]))
            continue
 
        # Case 3: on both sides -> compare the bars
        sheet = plan.get("feuillet") or "UNKNOWN"
        review = reinforcement_review_reasons(plan.get("armature"), shop.get("armature"))
        issues = compare_armature(plan.get("armature"), shop.get("armature"))
        if review and not issues:
            results[sheet]["a_verifier"] += 1
            results[sheet]["discrepancies"].append(_entry(
                plan, shop, "À VÉRIFIER", review))
            continue
        issues.extend(f"Requires review: {reason}" for reason in review)
 
        if len(plan_records) > 1 or len(shop_records) > 1:
            note = (f"Note: {len(plan_records)} plan record(s) and {len(shop_records)} "
                    f"shop record(s) share this name and were merged")
            if issues:
                issues.append(note)
 
        if issues:
            results[sheet]["non_conforme"] += 1
            results[sheet]["discrepancies"].append(_entry(plan, shop, "NON-CONFORME", issues))
        else:
            results[sheet]["conforme"] += 1
 
    return dict(sorted(results.items()))
