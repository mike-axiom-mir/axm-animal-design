import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.bilateral_mirror_surface_topology import (
    _face_correspondence,
    derive_exact_mirror_surface_candidate,
)
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)


def _load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class BilateralMirrorSurfaceTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = _load("examples/quadruped_neutral_001.json")
        cls.left_profile = _load("examples/quadruped_elbow_source_successor_003.json")
        cls.bilateral_profile = _load("examples/quadruped_elbow_bilateral_successor_003.json")
        cls.left, cls.right, cls.prerequisite = build_bilateral_source_successor_topology_rebind(
            cls.spec, cls.left_profile, cls.bilateral_profile
        )

    def test_historical_right_surface_is_not_exact_face_mirror(self):
        result = _face_correspondence(self.left, self.right)
        self.assertFalse(result["all_exact"])
        self.assertEqual(result["triangle_count"], 80)

    def test_candidate_preserves_positions_and_counts(self):
        candidate, record = derive_exact_mirror_surface_candidate(self.left, self.right)
        self.assertEqual(record["state"], "PASS_EXACT_MIRROR_SURFACE_TOPOLOGY_CANDIDATE")
        self.assertEqual(candidate["positions"], self.right["positions"])
        self.assertEqual(candidate["path_points"], self.right["path_points"])
        self.assertEqual(candidate["radii"], self.right["radii"])
        self.assertEqual(candidate["segments"], self.right["segments"])
        self.assertEqual(len(candidate["positions"]), 42)
        self.assertEqual(len(candidate["indices"]) // 3, 80)

    def test_candidate_is_exact_orientation_correct_mirror_face_set(self):
        candidate, record = derive_exact_mirror_surface_candidate(self.left, self.right)
        self.assertTrue(record["face_correspondence"]["all_exact"])
        self.assertEqual(record["face_correspondence"]["exact_triangle_record_matches"], 80)
        self.assertEqual(record["face_correspondence"]["exact_unoriented_triangle_matches"], 80)
        self.assertEqual(record["longitudinal_quad_count"], 30)
        self.assertEqual(record["unchanged_unoriented_triangle_sets"], 20)
        self.assertEqual(record["replaced_unoriented_triangle_sets"], 60)

    def test_candidate_keeps_local_geometry_gates_green(self):
        _candidate, record = derive_exact_mirror_surface_candidate(self.left, self.right)
        self.assertEqual(record["vertex_fans"]["disconnected_vertex_fan_count"], 0)
        self.assertEqual(record["vertex_fans"]["isolated_vertex_count"], 0)
        self.assertEqual(record["static_self_intersections"]["self_intersection_pair_count"], 0)
        self.assertTrue(all(value == "PASS" for value in record["gates"].values()))


if __name__ == "__main__":
    unittest.main()
