import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "src"))

from match import match_and_reconcile

# sheet -> (conforme, non_conforme, manquant, ajoute)
EXPECTED_COUNTS = {
    "S-100": (0, 1, 0, 0),
    "S-300": (2, 1, 0, 0),
    "S-400": (1, 1, 1, 0),
    # C-09 has a missing quantity; C-10 has no reinforcement extraction.
    # Neither establishes a confirmed discrepancy: both require review.
    "S-500": (2, 8, 1, 1),
    "S-600": (1, 1, 0, 0),
}

EXPECTED_STATUS = {
    "C-02": "NON-CONFORME",
    "C-06": "MANQUANT",
    "C-99": "AJOUTÉ",
    "M-01": "MANQUANT",
    "C-09": "À VÉRIFIER",
    "C-10": "À VÉRIFIER",
}


def load_result():
    records = json.loads((HERE / "sample_cases.json").read_text(encoding="utf-8"))
    return match_and_reconcile(records)


def test_counts_per_sheet():
    result = load_result()
    got = {sheet: (s["conforme"], s["non_conforme"], s["manquant"], s["ajoute"])
           for sheet, s in result.items()}
    assert got == EXPECTED_COUNTS
    assert result["S-500"]["a_verifier"] == 2


def test_specific_statuses():
    result = load_result()
    statuses = {item["element"]: item["status"]
                for stats in result.values() for item in stats["discrepancies"]}
    for element, status in EXPECTED_STATUS.items():
        assert statuses[element] == status


class MatchFixtureTests(unittest.TestCase):
    def test_counts_per_sheet(self):
        test_counts_per_sheet()

    def test_specific_statuses(self):
        test_specific_statuses()


if __name__ == "__main__":
    unittest.main()
