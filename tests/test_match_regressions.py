import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from match import match_and_reconcile

def bar(q=None, d=None, length=None):
    return dict(repere=None, quantite=q, diametre=d, longueur_mm=length, espacement_mm=None)

def record(source, sheet, bars, page=1):
    return dict(id=source+sheet, source=source, fichier=source+'.pdf', feuillet=sheet,
                page=page, x=10, y=10, type_element='colonne', element='C-1', armature=bars)

class MatchingRegressionTests(unittest.TestCase):
    def compare(self, left, right):
        return match_and_reconcile([record('plan','S-500',left),record('atelier','DA-1',right)])['S-500']
    def test_swapped_diameter_quantities(self):
        result=self.compare([bar(3,'15M'),bar(5,'25M')],[bar(5,'15M'),bar(3,'25M')])
        self.assertEqual(result['non_conforme'],1)
        self.assertEqual(len(result['discrepancies'][0]['issues']),2)
    def test_swapped_length_quantities(self):
        result=self.compare([bar(3,'15M',1000),bar(5,'15M',2000)],
                            [bar(5,'15M',1000),bar(3,'15M',2000)])
        self.assertEqual(result['non_conforme'],1)
    def test_reordered_and_split_bars_conform(self):
        result=self.compare([bar(3,'15M'),bar(5,'25M')],
                            [bar(2,'25M'),bar(3,'15M'),bar(3,'25M')])
        self.assertEqual(result['conforme'],1)
    def test_unknown_values_review(self):
        result=self.compare([bar()],[bar()])
        self.assertEqual(result['conforme'],0)
        self.assertEqual(result['a_verifier'],1)
    def test_repeated_identifiers_review_each_plan_sheet(self):
        records=[record(s,sh,[bar(3,'15M')]) for sh in ('S-500','S-501') for s in ('plan','atelier')]
        result=match_and_reconcile(records)
        self.assertEqual(set(result),{'S-500','S-501'})
        for stats in result.values():
            self.assertEqual(stats['a_verifier'],1)
            self.assertEqual(stats['conforme'],0)
    def test_unknown_quantity_not_summed_as_zero(self):
        result=self.compare([bar(None,'15M'),bar(5,'25M')],[bar(3,'15M'),bar(5,'25M')])
        self.assertEqual(result['a_verifier'],1)

    def test_shared_mark_keeps_quantity_property_relationship(self):
        left=[bar(3,'15M'),bar(5,'25M')]
        right=[bar(5,'15M'),bar(3,'25M')]
        for b in left+right: b['repere']='A'
        self.assertEqual(self.compare(left,right)['non_conforme'],1)

    def test_empty_extraction_review(self):
        self.assertEqual(self.compare([],[])['a_verifier'],1)

    def test_missing_diameter_is_extraction_uncertainty(self):
        result=self.compare([bar(8,'25M')],[bar(8)])
        self.assertEqual(result['a_verifier'],1)
        self.assertEqual(result['non_conforme'],0)

    def test_known_discrepancy_survives_unrelated_unknown_bar(self):
        left=[bar(8,'25M'),bar()];right=[bar(6,'25M'),bar()]
        for items in (left,right):
            items[0]['repere']='A';items[1]['repere']='B'
        result=self.compare(left,right)
        self.assertEqual(result['non_conforme'],1)
        self.assertTrue(any('quantity' in x for x in result['discrepancies'][0]['issues']))

    def test_repeated_missing_instances_stay_missing(self):
        result=match_and_reconcile([record('plan',s,[bar(8,'25M')]) for s in ('S-500','S-501')])
        for stats in result.values():
            self.assertEqual(stats['manquant'],1)
            self.assertEqual(stats['a_verifier'],0)

    def test_single_length_difference_is_reported_as_length(self):
        result=self.compare([bar(8,'25M',3600)],[bar(8,'25M',3500)])
        issues=result['discrepancies'][0]['issues']
        self.assertEqual(len(issues),1)
        self.assertIn('length (mm)',issues[0])

if __name__ == '__main__':
    unittest.main()
