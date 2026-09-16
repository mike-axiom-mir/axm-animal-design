from __future__ import annotations

import json
import unittest
from pathlib import Path

from axm_animal_design.organic_elbow_relief import (
    BASELINE_CANDIDATE_DIGEST,
    BEND_PLANE_RADIUS_M,
    CANDIDATE_DIGEST,
    CANDIDATE_ID,
    NOMINAL_ELBOW_RADIUS_M,
    RIG_PLAN_DIGEST,
    SOURCE_DIGEST,
    build_elbow_relief_candidate,
    digest,
    inspect_elbow_relief_review,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = json.loads((ROOT / "examples" / "quadruped_neutral_001.json").read_text(encoding="utf-8"))
RIG_DONOR = ROOT / ".test-rig-donor.json"


def _plan_from_env_or_fixture():
    import os
    value = os.environ.get("AXM_RIG_PLAN")
    if value:
        return json.loads(Path(value).read_text(encoding="utf-8"))
    # Unit tests remain runnable on stacked branches where the external rig plan is
    # not present. This exact fixture is the pinned PR #2 contract consumed by CI.
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


class OrganicElbowReliefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = _plan_from_env_or_fixture()
        # Local fallback fixture cannot impersonate the exact retained donor digest;
        # tests that require the exact donor are skipped unless CI supplies it.
        cls.has_exact_plan = digest(cls.plan) == RIG_PLAN_DIGEST

    def test_source_identity_is_pinned(self):
        self.assertEqual(digest(SOURCE), SOURCE_DIGEST)
        self.assertEqual(NOMINAL_ELBOW_RADIUS_M, 0.09)
        self.assertEqual(BEND_PLANE_RADIUS_M, 0.085)

    def test_candidate_scope_and_identity_with_exact_plan(self):
        if not self.has_exact_plan:
            self.skipTest("exact PR #2 rig plan supplied only by evidence workflow")
        candidate, scope = build_elbow_relief_candidate(SOURCE, self.plan)
        self.assertEqual(candidate["id"], CANDIDATE_ID)
        self.assertEqual(digest(candidate), CANDIDATE_DIGEST)
        self.assertEqual(candidate["organic_review"]["source_candidate_digest"], BASELINE_CANDIDATE_DIGEST)
        self.assertEqual(scope["moved_vertex_count"], 10)
        self.assertEqual(scope["moved_vertex_indices"], list(range(11, 21)))
        self.assertTrue(scope["global_bounds_unchanged"])
        self.assertLessEqual(scope["maximum_neutral_vertex_delta_m"], 0.00500001)

    def test_sampled_edge_envelope_improves_without_hidden_pass(self):
        if not self.has_exact_plan:
            self.skipTest("exact PR #2 rig plan supplied only by evidence workflow")
        receipt = inspect_elbow_relief_review(SOURCE, self.plan)
        self.assertEqual(receipt["decision"], "PASS_BOUNDED_ELBOW_BEND_PLANE_RELIEF_REVIEW_CANDIDATE")
        self.assertEqual(receipt["candidate"]["structural_gate"], "PASS")
        for row in receipt["comparisons"]:
            if row["angle_deg"] == 0.0:
                continue
            self.assertGreater(row["candidate_min_edge"], row["baseline_min_edge"])
            self.assertLess(row["candidate_max_edge"], row["baseline_max_edge"])
            # Area behavior is intentionally recorded rather than promoted to an
            # acceptance claim. The current candidate has a small negative minimum
            # area delta and CI must keep that visible.
            self.assertLessEqual(row["min_area_delta"], 0.0)

    def test_wrong_plan_fails_closed(self):
        if not self.has_exact_plan:
            self.skipTest("exact PR #2 rig plan supplied only by evidence workflow")
        broken = json.loads(json.dumps(self.plan))
        broken["joints"][0]["influence_radius"] = 0.12
        with self.assertRaisesRegex(ValueError, "rig plan identity drift"):
            build_elbow_relief_candidate(SOURCE, broken)


if __name__ == "__main__":
    unittest.main()
