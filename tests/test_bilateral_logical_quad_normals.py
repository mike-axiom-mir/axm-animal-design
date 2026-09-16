import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.bilateral_logical_quad_normals import (
    derive_logical_quad_normals,
    generated_triangle_smooth_normals,
    inspect_bilateral_logical_quad_normal_field,
    mirrored_normal_residual,
)
from axm_animal_design.bilateral_mirror_surface_topology import (
    derive_exact_mirror_surface_candidate,
)
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)


def _load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class BilateralLogicalQuadNormalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = _load("examples/quadruped_neutral_001.json")
        cls.left_profile = _load("examples/quadruped_elbow_source_successor_003.json")
        cls.bilateral_profile = _load("examples/quadruped_elbow_bilateral_successor_003.json")
        cls.left, cls.historical_right, cls.prerequisite = build_bilateral_source_successor_topology_rebind(
            cls.spec, cls.left_profile, cls.bilateral_profile
        )
        cls.exact_right, cls.topology = derive_exact_mirror_surface_candidate(
            cls.left, cls.historical_right
        )

    def test_candidate_is_diagonal_invariant_on_same_position_field(self):
        historical = derive_logical_quad_normals(self.historical_right)
        exact = derive_logical_quad_normals(self.exact_right)
        self.assertNotEqual(self.historical_right["indices"], self.exact_right["indices"])
        self.assertEqual(self.historical_right["positions"], self.exact_right["positions"])
        self.assertEqual(historical["normals"], exact["normals"])
        self.assertEqual(historical["tangent_policy"], "NOT_DEFINED_NO_UV_BASIS")

    def test_candidate_is_bilateral_mirror_and_outward(self):
        left = derive_logical_quad_normals(self.left)
        right = derive_logical_quad_normals(self.exact_right)
        self.assertLessEqual(mirrored_normal_residual(self.left, left["normals"], right["normals"]), 1e-10)
        self.assertGreater(left["minimum_ring_outward_radial_dot"], 0.0)
        self.assertGreater(right["minimum_ring_outward_radial_dot"], 0.0)
        self.assertLessEqual(left["maximum_unit_length_error"], 1e-10)
        self.assertLessEqual(right["maximum_unit_length_error"], 1e-10)

    def test_triangle_generated_normals_remain_connectivity_sensitive_control(self):
        historical = generated_triangle_smooth_normals(self.historical_right)
        exact = generated_triangle_smooth_normals(self.exact_right)
        self.assertNotEqual(historical, exact)

    def test_full_exact_animal_gate_passes_without_claiming_tangents(self):
        left, historical, exact, record = inspect_bilateral_logical_quad_normal_field(
            self.spec, self.left_profile, self.bilateral_profile
        )
        self.assertEqual(
            record["state"],
            "PASS_BILATERAL_LOGICAL_QUAD_NORMAL_FIELD_CANDIDATE__TANGENTS_HELD",
        )
        self.assertEqual(record["diagonal_invariance_max_normal_residual"], 0.0)
        self.assertLessEqual(record["bilateral_mirror_max_normal_residual"], 1e-10)
        self.assertGreater(record["triangle_generated_historical_vs_exact_max_normal_residual"], 0.0)
        self.assertFalse(record["truth_boundary"]["tangents_or_uvs_authored"])
        self.assertEqual(left["normal_count"], 42)
        self.assertEqual(historical["normal_count"], 42)
        self.assertEqual(exact["normal_count"], 42)


if __name__ == "__main__":
    unittest.main()
