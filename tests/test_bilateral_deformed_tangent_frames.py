from __future__ import annotations

import copy
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.bilateral_deformed_tangent_frames import (
    PASS_STATE,
    TANGENT_TOLERANCE,
    inspect_bilateral_deformed_tangent_frames,
)
from axm_animal_design.bilateral_source_successor_rigging_rebind import CANDIDATE_WEIGHTING
from axm_animal_design.connected_deformation import BASELINE_WEIGHTING

RIG_PLAN = os.environ.get("AXM_RIG_PLAN")
WEIGHTING_PROFILE = os.environ.get("AXM_WEIGHTING_PROFILE")


@unittest.skipUnless(RIG_PLAN and WEIGHTING_PROFILE, "exact Rigging donor paths are required")
class BilateralDeformedTangentFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text(encoding="utf-8"))
        cls.left_profile = json.loads((ROOT / "examples/quadruped_elbow_source_successor_003.json").read_text(encoding="utf-8"))
        cls.bilateral_profile = json.loads((ROOT / "examples/quadruped_elbow_bilateral_successor_003.json").read_text(encoding="utf-8"))
        cls.plan = json.loads(Path(RIG_PLAN).read_text(encoding="utf-8"))
        cls.weighting_profile = json.loads(Path(WEIGHTING_PROFILE).read_text(encoding="utf-8"))
        cls.receipt = inspect_bilateral_deformed_tangent_frames(
            cls.spec,
            cls.left_profile,
            cls.bilateral_profile,
            cls.plan,
            cls.weighting_profile,
        )

    def test_dense_deformed_tangent_frame_observer_passes(self):
        self.assertEqual(self.receipt["state"], PASS_STATE)
        self.assertEqual(self.receipt["total_pose_fields"], 484)
        self.assertEqual(self.receipt["render_vertices_per_pose"], 84)
        self.assertEqual(self.receipt["total_tangent_vectors_observed"], 40656)
        for side in ("left", "right"):
            for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
                row = self.receipt[side][weighting]
                self.assertEqual(row["dense_pose_count"], 121)
                self.assertEqual(row["render_vertices_per_pose"], 84)
                self.assertEqual(row["tangent_vectors_observed"], 10164)
                self.assertEqual(row["gate"], "PASS_DEFORMED_TANGENT_FRAME_DENSE_SWEEP")

    def test_uvs_stay_exact_and_neutral_reproduces_geometry_frame(self):
        for side in ("left", "right"):
            for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
                row = self.receipt[side][weighting]
                self.assertLessEqual(row["maximum_uv_residual"], TANGENT_TOLERANCE)
                self.assertLessEqual(row["neutral_static_tangent_max_residual"], TANGENT_TOLERANCE)
                self.assertLessEqual(row["neutral_static_normal_max_residual"], TANGENT_TOLERANCE)
                self.assertLessEqual(row["maximum_tangent_unit_length_error"], TANGENT_TOLERANCE)
                self.assertLessEqual(row["maximum_tangent_normal_dot_abs"], TANGENT_TOLERANCE)
                self.assertEqual(row["handedness_drift_count"], 0)

    def test_adjacent_integer_degree_samples_do_not_flip_tangent_direction(self):
        for side in ("left", "right"):
            for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
                self.assertGreater(self.receipt[side][weighting]["minimum_adjacent_sample_tangent_dot"], 0.0)

    def test_bilateral_deformed_tangent_frames_mirror_with_reflection_handedness(self):
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
            mirror = self.receipt["bilateral_mirror_evidence"][weighting]
            self.assertEqual(mirror["gate"], "PASS_EXACT_MIRRORED_DEFORMED_TANGENT_FRAMES")
            self.assertLessEqual(mirror["maximum_mirrored_position_residual_m"], TANGENT_TOLERANCE)
            self.assertLessEqual(mirror["maximum_mirrored_normal_residual"], TANGENT_TOLERANCE)
            self.assertLessEqual(mirror["maximum_uv_residual"], TANGENT_TOLERANCE)
            self.assertLessEqual(mirror["maximum_mirrored_tangent_xyz_residual"], TANGENT_TOLERANCE)
            self.assertEqual(mirror["tangent_handedness_mismatch_count"], 0)

    def test_weighting_identity_drift_fails_closed(self):
        drifted = copy.deepcopy(self.weighting_profile)
        drifted["candidate_exponent"] = 0.74
        with self.assertRaisesRegex(ValueError, "candidate exponent drift|weighting profile digest drift"):
            inspect_bilateral_deformed_tangent_frames(
                self.spec,
                self.left_profile,
                self.bilateral_profile,
                self.plan,
                drifted,
            )

    def test_truth_boundary_keeps_visual_animation_transport_and_runtime_separate(self):
        truth = self.receipt["truth_boundary"]
        self.assertFalse(truth["source_or_topology_modified_by_rigging"])
        self.assertFalse(truth["rig_or_weights_modified"])
        self.assertFalse(truth["geometry_uv_policy_modified"])
        self.assertFalse(truth["geometry_normal_policy_modified"])
        self.assertTrue(truth["geometry_structural_tangent_basis_consumed"])
        self.assertTrue(truth["deformed_tangent_frame_observer_established"])
        self.assertFalse(truth["production_skin_tangent_transport_established"])
        self.assertFalse(truth["tangent_space_normal_map_rendered"])
        self.assertFalse(truth["shaded_deformed_visual_quality_accepted"])
        self.assertFalse(truth["animation_accepted"])
        self.assertFalse(truth["technical_art_transport_accepted"])
        self.assertFalse(truth["runtime_or_controller_accepted"])
        self.assertFalse(truth["canon_claimed"])


if __name__ == "__main__":
    unittest.main()
