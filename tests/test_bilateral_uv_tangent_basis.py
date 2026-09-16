import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.bilateral_uv_tangent_basis import (
    derive_uv_tangent_basis,
    inspect_bilateral_uv_tangent_basis,
)
from axm_animal_design.bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from axm_animal_design.bilateral_source_successor_topology_rebind import build_bilateral_source_successor_topology_rebind


def _load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class BilateralUvTangentBasisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = _load("examples/quadruped_neutral_001.json")
        cls.left_profile = _load("examples/quadruped_elbow_source_successor_003.json")
        cls.bilateral_profile = _load("examples/quadruped_elbow_bilateral_successor_003.json")
        cls.left, cls.historical_right, cls.prerequisite = build_bilateral_source_successor_topology_rebind(
            cls.spec, cls.left_profile, cls.bilateral_profile
        )
        cls.exact_right, cls.topology = derive_exact_mirror_surface_candidate(cls.left, cls.historical_right)

    def test_render_domain_splits_uv_seam_and_cap_poles_without_moving_source_surface(self):
        basis = derive_uv_tangent_basis(self.left, side="left")
        self.assertEqual(basis["source_vertex_count"], 42)
        self.assertEqual(basis["render_vertex_count"], 84)
        self.assertEqual(basis["triangle_count"], 80)
        self.assertTrue(basis["source_triangle_records_preserved"])
        self.assertTrue(basis["source_triangle_positions_preserved"])
        self.assertTrue(basis["uvs_within_unit_square"])
        self.assertGreater(basis["minimum_uv_triangle_area"], 0.0)

    def test_side_seam_reduces_wrap_span_from_naive_control(self):
        basis = derive_uv_tangent_basis(self.left, side="left")
        self.assertAlmostEqual(basis["maximum_side_triangle_u_span"], 0.1, places=10)
        self.assertAlmostEqual(basis["naive_unsplit_maximum_side_triangle_u_span"], 0.9, places=10)

    def test_tangents_are_unit_and_orthogonal_to_selected_explicit_normals(self):
        for candidate, side in ((self.left, "left"), (self.exact_right, "right")):
            basis = derive_uv_tangent_basis(candidate, side=side)
            self.assertLessEqual(basis["maximum_tangent_unit_length_error"], 1e-9)
            self.assertLessEqual(basis["maximum_tangent_normal_dot_abs"], 1e-9)
            self.assertEqual(len(basis["render_tangents"]), basis["render_vertex_count"])
            self.assertTrue(all(abs(tangent[3]) == 1.0 for tangent in basis["render_tangents"]))

    def test_full_bilateral_gate_requires_mirrored_xyz_and_reflection_handedness(self):
        left, right, record = inspect_bilateral_uv_tangent_basis(
            self.spec, self.left_profile, self.bilateral_profile
        )
        self.assertEqual(
            record["state"],
            "PASS_BILATERAL_UV_TANGENT_BASIS_CANDIDATE__FINAL_UV_VISUAL_TRANSPORT_HELD",
        )
        self.assertEqual(left["render_vertex_count"], right["render_vertex_count"])
        self.assertLessEqual(record["bilateral"]["maximum_mirrored_position_residual"], 1e-9)
        self.assertLessEqual(record["bilateral"]["maximum_mirrored_normal_residual"], 1e-9)
        self.assertLessEqual(record["bilateral"]["maximum_uv_residual"], 1e-9)
        self.assertLessEqual(record["bilateral"]["maximum_mirrored_tangent_xyz_residual"], 1e-9)
        self.assertEqual(record["bilateral"]["tangent_handedness_mismatch_count"], 0)

    def test_truth_boundary_does_not_promote_structural_uvs_to_final_surface_acceptance(self):
        _left, _right, record = inspect_bilateral_uv_tangent_basis(
            self.spec, self.left_profile, self.bilateral_profile
        )
        boundary = record["truth_boundary"]
        self.assertTrue(boundary["structural_uv_basis_authored"])
        self.assertTrue(boundary["structural_tangent_basis_authored"])
        self.assertFalse(boundary["final_texture_uv_or_texel_density_accepted"])
        self.assertFalse(boundary["tangent_space_normal_map_rendered"])
        self.assertFalse(boundary["deformed_shaded_quality_checked"])
        self.assertFalse(boundary["technical_art_transport_checked"])
        self.assertFalse(boundary["runtime_storage_or_performance_accepted"])
        self.assertFalse(boundary["canon_claimed"])


if __name__ == "__main__":
    unittest.main()
