import copy
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.weighting_refinement import compare_weighting_profiles

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
PLAN = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())
CANDIDATE = json.loads((ROOT / "examples/quadruped_weighting_refinement_001.json").read_text())


class WeightingRefinementTests(unittest.TestCase):
    def test_candidate_is_deterministic_and_exact_identity_bound(self):
        first = compare_weighting_profiles(SPEC, PLAN, CANDIDATE)
        second = compare_weighting_profiles(SPEC, PLAN, CANDIDATE)
        self.assertEqual(first, second)
        self.assertEqual(first["gate"], "PASS_SCOPED_WEIGHTING_REFINEMENT")
        self.assertEqual(first["baseline_plan_digest"], CANDIDATE["baseline_plan_digest"])
        self.assertEqual(first["joint_count"], 4)
        self.assertEqual(first["sampled_pose_count"], 12)
        self.assertEqual(first["nonzero_comparison_count"], 8)

    def test_every_extreme_pose_improves_bounded_distortion_metrics(self):
        report = compare_weighting_profiles(SPEC, PLAN, CANDIDATE)
        for row in report["nonzero_pose_comparisons"]:
            self.assertEqual(row["status"], "PASS_IMPROVED")
            self.assertGreater(row["minimum_triangle_area_ratio_gain"], 0.0)
            self.assertGreater(row["maximum_edge_length_ratio_reduction"], 0.0)
            self.assertGreaterEqual(row["minimum_edge_length_ratio_gain"], 0.0)

    def test_candidate_preserves_chain_and_transform_invariants(self):
        report = compare_weighting_profiles(SPEC, PLAN, CANDIDATE)
        for joint in report["joints"]:
            self.assertEqual(joint["status"], "PASS")
            self.assertLessEqual(joint["max_weight_sum_error"], 1e-12)
            self.assertGreater(joint["weight_counts"]["fixed"], 0)
            self.assertGreater(joint["weight_counts"]["blended"], 0)
            self.assertGreater(joint["weight_counts"]["rigid"], 0)
            for pose in joint["poses"]:
                self.assertEqual(pose["status"], "PASS")
                self.assertEqual(pose["collapsed_triangles"], 0)
                self.assertLessEqual(pose["fixed_weight_vertex_max_drift"], 1e-9)
                self.assertLessEqual(pose["rigid_weight_radius_max_drift"], 1e-9)
                for downstream in pose["downstream_regions"]:
                    self.assertEqual(downstream["status"], "PASS")
                for continuity in pose["chain_continuity"]:
                    self.assertEqual(continuity["status"], "PASS")
                    self.assertLessEqual(continuity["absolute_gap_drift"], continuity["tolerance"])

    def test_neutral_pose_is_numerically_equivalent(self):
        report = compare_weighting_profiles(SPEC, PLAN, CANDIDATE)
        for joint in report["joints"]:
            neutral = next(row for row in joint["poses"] if row["angle_deg"] == 0.0)
            self.assertEqual(neutral["comparison_status"], "PASS_NEUTRAL_EQUIVALENT")
            self.assertEqual(neutral["minimum_triangle_area_ratio"], 1.0)
            self.assertEqual(neutral["minimum_edge_length_ratio"], 1.0)
            self.assertEqual(neutral["maximum_edge_length_ratio"], 1.0)

    def test_wrong_baseline_identity_fails_closed(self):
        changed = copy.deepcopy(CANDIDATE)
        changed["baseline_plan_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "baseline_plan_digest"):
            compare_weighting_profiles(SPEC, PLAN, changed)

    def test_unsupported_profile_fails_closed(self):
        changed = copy.deepcopy(CANDIDATE)
        changed["candidate_profile"] = "invented-profile"
        with self.assertRaisesRegex(ValueError, "candidate_profile"):
            compare_weighting_profiles(SPEC, PLAN, changed)


if __name__ == "__main__":
    unittest.main()
