import copy
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.organic_form import build_form_study, inspect_intent, project_wire_svg

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())


class OrganicFormTests(unittest.TestCase):
    def test_baseline_is_deterministic_and_declared_intent_passes(self):
        first = build_form_study(SPEC)
        second = build_form_study(SPEC)
        self.assertEqual(first["source_digest"], second["source_digest"])
        self.assertEqual(first["surface_digest"], second["surface_digest"])
        self.assertEqual(first["gates"]["declared-proportion-and-symmetry-intent"], "PASS")
        self.assertEqual(first["counts"]["regions"], 20)
        self.assertGreater(first["counts"]["triangles"], 1000)
        self.assertGreater(first["counts"]["vertices"], 500)

    def test_every_triangle_index_is_bounded_and_non_degenerate(self):
        evidence = build_form_study(SPEC)
        for primitive in evidence["surface"]["primitives"]:
            positions = primitive["positions"]
            indices = primitive["indices"]
            self.assertEqual(len(indices) % 3, 0)
            self.assertTrue(all(0 <= index < len(positions) for index in indices))
            for offset in range(0, len(indices), 3):
                a, b, c = (positions[indices[offset]], positions[indices[offset + 1]], positions[indices[offset + 2]])
                ab = [b[i] - a[i] for i in range(3)]
                ac = [c[i] - a[i] for i in range(3)]
                cross = [
                    ab[1] * ac[2] - ab[2] * ac[1],
                    ab[2] * ac[0] - ab[0] * ac[2],
                    ab[0] * ac[1] - ab[1] * ac[0],
                ]
                self.assertGreater(sum(value * value for value in cross), 1e-16)

    def test_bilateral_drift_is_reported_not_repaired(self):
        changed = copy.deepcopy(SPEC)
        changed["landmarks"]["elbow_R"][0] += 0.04
        report = inspect_intent(changed)
        row = next(item for item in report["bilateral_pairs"] if item["id"] == "elbow-mirror")
        self.assertEqual(row["status"], "FAIL")
        self.assertEqual(report["declared_intent_status"], "FAIL")

    def test_bend_zones_stay_declared_not_deformation_tested(self):
        report = inspect_intent(SPEC)
        self.assertEqual(len(report["bend_zones"]), 4)
        self.assertTrue(all(item["status"] == "DECLARED_NOT_DEFORMATION_TESTED" for item in report["bend_zones"]))

    def test_wire_projection_comes_from_generated_geometry(self):
        evidence = build_form_study(SPEC)
        side = project_wire_svg(evidence, "side")
        front = project_wire_svg(evidence, "front")
        self.assertIn("<svg", side)
        self.assertIn("<line", side)
        self.assertIn("quadruped-neutral-001", side)
        self.assertNotEqual(side, front)


if __name__ == "__main__":
    unittest.main()
