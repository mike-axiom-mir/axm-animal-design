from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from axm_animal_design.connected_deformation import digest
from axm_animal_design.organic_elbow_balanced_relief import (
    CANDIDATE_DIGEST,
    RIG_PLAN_DIGEST,
    SOURCE_DIGEST,
)
from axm_animal_design.organic_elbow_balanced_sweep import (
    EVIDENCE_SCHEMA,
    POSE_SCHEDULE_DEG,
    WEIGHTING_PROFILES,
    inspect_balanced_dense_sweep,
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


class OrganicElbowBalancedDenseSweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = _plan_from_env_or_fixture()
        cls.has_exact_plan = digest(cls.plan) == RIG_PLAN_DIGEST

    def test_schedule_is_bounded_dense_and_symmetric(self):
        self.assertEqual(POSE_SCHEDULE_DEG[0], -60.0)
        self.assertEqual(POSE_SCHEDULE_DEG[-1], 60.0)
        self.assertEqual(len(POSE_SCHEDULE_DEG), 25)
        self.assertEqual(POSE_SCHEDULE_DEG[12], 0.0)
        self.assertEqual(
            tuple(
                round(POSE_SCHEDULE_DEG[index + 1] - POSE_SCHEDULE_DEG[index], 12)
                for index in range(24)
            ),
            (5.0,) * 24,
        )
        self.assertEqual(
            WEIGHTING_PROFILES,
            ("smoothstep-v0", "ease-out-power-0p75-v1"),
        )

    def test_dense_sweep_retains_exact_candidate_and_reports_all_samples(self):
        if not self.has_exact_plan:
            self.skipTest("exact PR #2 rig plan supplied only by evidence workflow")
        self.assertEqual(digest(SOURCE), SOURCE_DIGEST)
        original_plan_digest = digest(self.plan)
        receipt = inspect_balanced_dense_sweep(SOURCE, self.plan)
        self.assertEqual(digest(self.plan), original_plan_digest)
        self.assertEqual(receipt["schema"], EVIDENCE_SCHEMA)
        self.assertEqual(receipt["balanced_candidate_digest"], CANDIDATE_DIGEST)
        self.assertEqual(receipt["pose_schedule_deg"], list(POSE_SCHEDULE_DEG))
        self.assertEqual(receipt["pose_sample_count_per_profile"], 25)
        self.assertEqual(len(receipt["comparisons"]), 50)
        self.assertFalse(
            receipt["observational_schedule_contract"]["source_rig_plan_mutated"]
        )
        self.assertTrue(
            receipt["observational_schedule_contract"][
                "observer_schedule_external_to_rig_plan"
            ]
        )
        self.assertIn(
            receipt["decision"],
            {
                "PASS_BALANCED_ELBOW_DENSE_SWEEP_DIRECTIONALLY_NONWORSE",
                "FAIL_BALANCED_ELBOW_DENSE_SWEEP_STRUCTURAL_GATE",
                "FAIL_BALANCED_ELBOW_DENSE_SWEEP_DIRECTIONAL_NONREGRESSION",
            },
        )
        for profile in WEIGHTING_PROFILES:
            rows = [
                row for row in receipt["comparisons"] if row["weighting"] == profile
            ]
            self.assertEqual(
                [row["angle_deg"] for row in rows], list(POSE_SCHEDULE_DEG)
            )

    def test_wrong_plan_fails_closed_before_sweep(self):
        if not self.has_exact_plan:
            self.skipTest("exact PR #2 rig plan supplied only by evidence workflow")
        broken = json.loads(json.dumps(self.plan))
        broken["joints"][0]["pose_angles_deg"] = [-60.0, -30.0, 0.0, 30.0, 60.0]
        with self.assertRaisesRegex(ValueError, "rig plan identity drift"):
            inspect_balanced_dense_sweep(SOURCE, broken)


if __name__ == "__main__":
    unittest.main()
