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
    quantities = [q for q in quantities if q is not None]
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
    """Return a sentence describing the difference, or None if all is fine.
    A value present on one side only IS reported: a missed error costs more
    than a false alarm."""
    if not plan_vals and not shop_vals:
        return None
    if not plan_vals:
        return f"{label}: no value on plan (shop = {_fmt(shop_vals)})"
    if not shop_vals:
        return f"{label}: no value on shop drawing (plan = {_fmt(plan_vals)})"
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
 
    if not plan_groups and not shop_groups:
        return ["No reinforcement data extracted on either side (cannot verify)"]
 
    checks = [
        ("quantity", _total_quantity, _equal_exact),
        ("diameter", _diameters, _equal_exact),
        ("spacing (mm)", lambda bars: _numbers(bars, "espacement_mm"), _numbers_close(SPACING_TOLERANCE_MM)),
        ("length (mm)", lambda bars: _numbers(bars, "longueur_mm"), _numbers_close(LENGTH_TOLERANCE_MM)),
    ]
 
    issues: List[str] = []
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
    return {"conforme": 0, "non_conforme": 0, "manquant": 0, "ajoute": 0, "discrepancies": []}
 
 
def match_and_reconcile(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    plans, shops = group_records(records)
    results: Dict[str, Dict[str, Any]] = defaultdict(_new_sheet_stats)
 
    for key in sorted(set(plans) | set(shops)):
        plan_records = plans.get(key, [])
        shop_records = shops.get(key, [])
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
        issues = compare_armature(plan.get("armature"), shop.get("armature"))
 
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
