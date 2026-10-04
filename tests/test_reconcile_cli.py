"""Reject invalid production JSON and accidental cloud/report destinations."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReconcileCliTests(unittest.TestCase):
    def run_cli(self, records, output=None):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input.json'
            target = output or Path(folder) / 'report.pdf'
            source.write_text(json.dumps(records), encoding='utf8')
            completed = subprocess.run(
                [sys.executable, str(ROOT / 'src/reconcile_cli.py'),
                 str(source), '--out', str(target)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 2)
            self.assertFalse(target.exists())
            return completed.stderr

    def test_rejects_invalid_annex_a(self):
        self.assertIn('not valid Annex A', self.run_cli([{'element': 'C-1'}]))

    def test_rejects_repository_output(self):
        self.assertIn('outside Git and OneDrive', self.run_cli([], ROOT / 'blocked-test-report.pdf'))

    def test_rejects_onedrive_output(self):
        self.assertIn('outside Git and OneDrive', self.run_cli(
            [], Path.home() / 'OneDrive' / 'blocked-test-report.pdf'))


if __name__ == '__main__':
    unittest.main()
