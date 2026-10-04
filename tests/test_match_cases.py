import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "src"))

from match import match_and_reconcile

# sheet -> (conforme, non_conforme, manquant, ajoute)
EXPECTED_COUNTS = {
    "S-100": (0, 1, 0, 0),
    "S-300": (2, 1, 0, 0),
    "S-400": (1, 1, 1, 0),
    "S-500": (2, 10, 1, 1),
    "S-600": (1, 1, 0, 0),
}

EXPECTED_STATUS = {
    "C-02": "NON-CONFORME",
    "C-06": "MANQUANT",
    "C-99": "AJOUTÉ",
    "M-01": "MANQUANT",
}


def load_result():
    records = json.loads((HERE / "sample_cases.json").read_text(encoding="utf-8"))
    return match_and_reconcile(records)


def test_counts_per_sheet():
    result = load_result()
    got = {sheet: (s["conforme"], s["non_conforme"], s["manquant"], s["ajoute"])
           for sheet, s in result.items()}
    assert got == EXPECTED_COUNTS


def test_specific_statuses():
    result = load_result()
    statuses = {item["element"]: item["status"]
                for stats in result.values() for item in stats["discrepancies"]}
    for element, status in EXPECTED_STATUS.items():
        assert statuses[element] == status


if __name__ == "__main__":
    test_counts_per_sheet()
    test_specific_statuses()
    print("All tests passed")