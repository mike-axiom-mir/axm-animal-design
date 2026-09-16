from __future__ import annotations

import copy
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.bilateral_deformed_logical_quad_normals import (
    NORMAL_TOLERANCE,
    PASS_STATE,
    inspect_bilateral_deformed_logical_quad_normals,
)
from axm_animal_design.bilateral_source_successor_rigging_rebind import CANDIDATE_WEIGHTING
from axm_animal_design.connected_deformation import BASELINE_WEIGHTING

RIG_PLAN = os.environ.get("AXM_RIG_PLAN")
WEIGHTING_PROFILE = os.environ.get("AXM_WEIGHTING_PROFILE")


@unittest.skipUnless(RIG_PLAN and WEIGHTING_PROFILE, "exact Rigging donor paths are required")
class BilateralDeformedLogicalQuadNormalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text(encoding="utf-8"))
        cls.left_profile = json.loads((ROOT / "examples/quadruped_elbow_source_successor_003.json").read_text(encoding="utf-8"))
        cls.bilateral_profile = json.loads((ROOT / "examples/quadruped_elbow_bilateral_successor_003.json").read_text(encoding="utf-8"))
        cls.plan = json.loads(Path(RIG_PLAN).read_text(encoding="utf-8"))
        cls.weighting_profile = json.loads(Path(WEIGHTING_PROFILE).read_text(encoding="utf-8"))
        cls.receipt = inspect_bilateral_deformed_logical_quad_normals(
            cls.spec,
            cls.left_profile,
            cls.bilateral_profile,
            cls.plan,
            cls.weighting_profile,
        )

    def test_dense_deformed_normal_field_passes(self):
        self.assertEqual(self.receipt["state"], PASS_STATE)
        self.assertEqual(self.receipt["total_pose_fields"], 484)
        self.assertEqual(self.receipt["total_normal_vectors_observed"], 20328)
        for side in ("left", "right"):
            for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
                row = self.receipt[side][weighting]
                self.assertEqual(row["dense_pose_count"], 121)
                self.assertEqual(row["normal_vectors_observed"], 5082)
                self.assertEqual(row["gate"], "PASS_DEFORMED_LOGICAL_QUAD_NORMAL_FIELD_DENSE_SWEEP")

    def test_neutral_matches_static_and_bilateral_normals_mirror(self):
        for side in ("left", "right"):
            for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
                self.assertLessEqual(
                    self.receipt[side][weighting]["neutral_static_normal_max_residual"],
                    NORMAL_TOLERANCE,
                )
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
            mirror = self.receipt["bilateral_mirror_evidence"][weighting]
            self.assertEqual(mirror["gate"], "PASS_EXACT_MIRRORED_POSES_AND_DEFORMED_NORMALS")
            self.assertLessEqual(mirror["maximum_mirrored_pose_residual_m"], NORMAL_TOLERANCE)
            self.assertLessEqual(mirror["maximum_mirrored_normal_residual"], NORMAL_TOLERANCE)

    def test_adjacent_integer_degree_samples_do_not_flip_normal_direction(self):
        for side in ("left", "right"):
            for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
                self.assertGreater(self.receipt[side][weighting]["minimum_adjacent_sample_normal_dot"], 0.0)

    def test_weighting_identity_drift_fails_closed(self):
        drifted = copy.deepcopy(self.weighting_profile)
        drifted["candidate_exponent"] = 0.74
        with self.assertRaisesRegex(ValueError, "candidate exponent drift|weighting profile digest drift"):
            inspect_bilateral_deformed_logical_quad_normals(
                self.spec,
                self.left_profile,
                self.bilateral_profile,
                self.plan,
                drifted,
            )

    def test_truth_boundary_keeps_animation_runtime_and_visual_acceptance_separate(self):
        truth = self.receipt["truth_boundary"]
        self.assertFalse(truth["source_or_topology_modified_by_rigging"])
        self.assertFalse(truth["rig_or_weights_modified"])
        self.assertFalse(truth["geometry_normal_policy_modified"])
        self.assertFalse(truth["tangent_policy_established"])
        self.assertFalse(truth["production_skin_normal_transport_established"])
        self.assertFalse(truth["shaded_deformed_visual_quality_accepted"])
        self.assertFalse(truth["animation_accepted"])
        self.assertFalse(truth["runtime_or_controller_accepted"])


if __name__ == "__main__":
    unittest.main()
