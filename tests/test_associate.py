import unittest
from l2c.associate import associate_annotations


class AssociationTests(unittest.TestCase):
    def setUp(self):
        self.page = dict(source="plan", fichier="synthetic.pdf", feuillet="S-100", page=1)
        self.annotation = dict(self.page, id="a", x=10, y=10,
                               armature=[dict(repere=None, diametre="25M", quantite=9,
                                              espacement_mm=None, longueur_mm=None)])
        self.element = dict(self.page, element="L-13", type_element="semelle", bbox=[0, 0, 20, 20])

    def test_other_page_does_not_associate(self):
        e = dict(self.element, page=2)
        self.assertEqual(associate_annotations([self.annotation], [e])["associations"][0]["status"], "unresolved")

    def test_overlap_is_ambiguous(self):
        other = dict(self.element, element="L-14")
        result = associate_annotations([self.annotation], [self.element, other])
        self.assertEqual(result["records"], [])
        self.assertEqual(result["associations"][0]["status"], "ambiguous")

    def test_shared_schedule_applies_to_multiple_elements(self):
        a = dict(self.annotation, x=100, y=100, schedule_ref="footings/C")
        elements = [dict(self.element, schedule_ref="footings/C"),
                    dict(self.element, element="L-14", schedule_ref="footings/C")]
        result = associate_annotations([a], elements)
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(len(set(r["id"] for r in result["records"])), 2)

    def test_conflicting_reference_and_geometry_abstains(self):
        a = dict(self.annotation, element_ref="L-14")
        other = dict(self.element, element="L-14", bbox=[50, 50, 60, 60])
        self.assertEqual(associate_annotations([a], [self.element, other])["records"], [])

    def test_leader_can_link_external_annotation(self):
        a = dict(self.annotation, x=100, y=100, leader_endpoint=[10, 10])
        self.assertEqual(associate_annotations([a], [self.element])["records"][0]["element"], "L-13")


if __name__ == "__main__":
    unittest.main()
