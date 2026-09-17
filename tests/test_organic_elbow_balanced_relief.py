from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from axm_animal_design.connected_deformation import digest
from axm_animal_design.organic_elbow_balanced_relief import (
    BEND_PLANE_RADIUS_M,
    CANDIDATE_DIGEST,
    CANDIDATE_ID,
    EDGE_IMPROVEMENT_FLOOR,
    JOINT_AXIS_WIDTH_SCALE,
    MAX_BOUND_EXPANSION_M,
    MAX_NEUTRAL_VERTEX_DELTA_M,
    RIG_PLAN_DIGEST,
    SOURCE_DIGEST,
    build_balanced_elbow_candidate,
    inspect_balanced_elbow_review,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = json.loads((ROOT / "examples" / "quadruped_neutral_001.json").read_text(encoding="utf-8"))


def _plan_from_env_or_fixture():
    value = os.environ.get("AXM_RIG_PLAN")
    if value:
        return json.loads(Path(value).read_text(encoding="utf-8"))
    return {
        "schema": "axm.animal-rig-deformation-plan/v0.1",
        "source_name": "quadruped-neutral-001",
        "joints": [
            {
                "id": "front-elbow-L",
                "landmark": "elbow_L",
                "parent_landmark": "shoulder_L",
                "child_landmark": "wrist_L",
                "parent_region": "front_upper_L",
                "child_region": "front_lower_L",
                "downstream_regions": ["front_paw_L"],
                "axis": [0.0, 1.0, 0.0],
                "influence_radius": 0.11,
                "pose_angles_deg": [-60.0, 0.0, 60.0],
            }
        ],
    }


class OrganicElbowBalancedReliefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = _plan_from_env_or_fixture()
        cls.has_exact_plan = digest(cls.plan) == RIG_PLAN_DIGEST

    def test_source_and_bounded_parameters_are_pinned(self):
        self.assertEqual(digest(SOURCE), SOURCE_DIGEST)
        self.assertEqual(BEND_PLANE_RADIUS_M, 0.0875)
        self.assertEqual(JOINT_AXIS_WIDTH_SCALE, 1.03)
        self.assertEqual(EDGE_IMPROVEMENT_FLOOR, 0.005)
        self.assertEqual(MAX_NEUTRAL_VERTEX_DELTA_M, 0.0028)
        self.assertEqual(MAX_BOUND_EXPANSION_M, 0.003)

    def test_candidate_scope_identity_and_explicit_bound_change(self):
        if not self.has_exact_plan:
            self.skipTest("exact PR #2 rig plan supplied only by evidence workflow")
        candidate, scope = build_balanced_elbow_candidate(SOURCE, self.plan)
        self.assertEqual(candidate["id"], CANDIDATE_ID)
        self.assertEqual(digest(candidate), CANDIDATE_DIGEST)
        self.assertEqual(scope["moved_vertex_indices"], list(range(11, 21)))
        self.assertEqual(scope["moved_vertex_count"], 10)
        self.assertLessEqual(scope["maximum_neutral_vertex_delta_m"], MAX_NEUTRAL_VERTEX_DELTA_M)
        self.assertFalse(scope["global_bounds_unchanged"])
        self.assertGreater(scope["maximum_positive_bound_expansion_m"], 0.0)
        self.assertLessEqual(scope["maximum_positive_bound_expansion_m"], MAX_BOUND_EXPANSION_M)
        self.assertFalse(candidate["organic_review"]["source_landmarks_changed"])
        self.assertFalse(candidate["organic_review"]["source_regions_changed"])

    def test_balanced_successor_closes_sampled_area_tradeoff_under_both_weightings(self):
        if not self.has_exact_plan:
            self.skipTest("exact PR #2 rig plan supplied only by evidence workflow")
        receipt = inspect_balanced_elbow_review(SOURCE, self.plan)
        self.assertEqual(
            receipt["decision"],
            "PASS_BALANCED_ELBOW_RELIEF_REMOVES_MIN_AREA_TRADEOFF_ACROSS_PINNED_WEIGHTINGS",
        )
        self.assertEqual(receipt["adoption_state"], "HOLD_VISUAL_AND_SOURCE_ADOPTION")
        for row in receipt["comparisons"]:
            if row["angle_deg"] == 0.0:
                self.assertEqual(row["comparison_gate"], "PASS_NEUTRAL_RATIOS")
                continue
            self.assertGreaterEqual(row["balanced_min_area_delta_vs_baseline"], 0.0)
            self.assertGreaterEqual(row["balanced_max_area_reduction_vs_baseline"], 0.0)
            self.assertGreaterEqual(row["balanced_min_edge_gain_vs_baseline"], EDGE_IMPROVEMENT_FLOOR)
            self.assertGreaterEqual(row["balanced_max_edge_reduction_vs_baseline"], EDGE_IMPROVEMENT_FLOOR)
            self.assertEqual(row["comparison_gate"], "PASS_AREA_NONWORSE_AND_MATERIAL_EDGE_IMPROVEMENT")

    def test_wrong_plan_fails_closed(self):
        if not self.has_exact_plan:
            self.skipTest("exact PR #2 rig plan supplied only by evidence workflow")
        broken = json.loads(json.dumps(self.plan))
        broken["joints"][0]["influence_radius"] = 0.12
        with self.assertRaisesRegex(ValueError, "rig plan identity drift"):
            build_balanced_elbow_candidate(SOURCE, broken)


if __name__ == "__main__":
    unittest.main()
