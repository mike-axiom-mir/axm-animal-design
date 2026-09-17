import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.self_intersection import inspect_triangle_self_intersections
from axm_animal_design.topology_study import build_connected_chain, derive_shared_ring_radii


class SelfIntersectionTests(unittest.TestCase):
    def setUp(self):
        spec = json.loads((ROOT / "examples" / "quadruped_neutral_001.json").read_text())
        derivation = derive_shared_ring_radii(
            spec["regions"],
            ("front_upper_L", "front_lower_L", "front_paw_L"),
        )
        self.mesh = build_connected_chain(
            "front-left-connected-chain-001",
            [spec["landmarks"][name] for name in derivation["path_landmarks"]],
            derivation["radii_m"],
            segments=10,
        )

    def test_exact_connected_candidate_has_no_nonadjacent_self_intersections(self):
        report = inspect_triangle_self_intersections(self.mesh["positions"], self.mesh["indices"])
        self.assertEqual(report["status"], "PASS_NO_NONADJACENT_SELF_INTERSECTIONS")
        self.assertEqual(report["self_intersection_pair_count"], 0)
        self.assertTrue(report["truth_boundary"]["nonadjacent_triangle_self_intersection_checked"])
        self.assertTrue(report["truth_boundary"]["topological_neighbor_contacts_excluded"])
        self.assertFalse(report["truth_boundary"]["continuous_deformation_checked"])

    def test_crossing_triangle_negative_control_is_detected(self):
        positions = [
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [0.0, 2.0, 0.0],
            [0.5, 0.5, -1.0],
            [0.5, 0.5, 1.0],
            [1.5, 0.5, 0.0],
        ]
        report = inspect_triangle_self_intersections(positions, [0, 1, 2, 3, 4, 5])
        self.assertEqual(report["status"], "SELF_INTERSECTIONS_DETECTED")
        self.assertEqual(report["self_intersection_pair_count"], 1)
        self.assertEqual(report["examples"], [{"triangle_a": 0, "triangle_b": 1}])

    def test_coplanar_overlap_negative_control_is_detected(self):
        positions = [
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [0.0, 2.0, 0.0],
            [0.25, 0.25, 0.0],
            [1.25, 0.25, 0.0],
            [0.25, 1.25, 0.0],
        ]
        report = inspect_triangle_self_intersections(positions, [0, 1, 2, 3, 4, 5])
        self.assertEqual(report["status"], "SELF_INTERSECTIONS_DETECTED")
        self.assertEqual(report["self_intersection_pair_count"], 1)

    def test_disjoint_triangles_pass(self):
        positions = [
            [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
            [0.0, 0.0, 2.0], [1.0, 0.0, 2.0], [0.0, 1.0, 2.0],
        ]
        report = inspect_triangle_self_intersections(positions, [0, 1, 2, 3, 4, 5])
        self.assertEqual(report["status"], "PASS_NO_NONADJACENT_SELF_INTERSECTIONS")
        self.assertEqual(report["self_intersection_pair_count"], 0)


if __name__ == "__main__":
    unittest.main()
