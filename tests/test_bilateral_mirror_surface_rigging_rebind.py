from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from axm_animal_design.bilateral_mirror_surface_rigging_rebind import (
    PASS_STATE,
    inspect_bilateral_mirror_surface_rigging_rebind,
)
from axm_animal_design.bilateral_source_successor_rigging_rebind import (
    CANDIDATE_WEIGHTING,
    MIRROR_TOLERANCE,
)
from axm_animal_design.connected_deformation import BASELINE_WEIGHTING

ROOT = Path(__file__).resolve().parents[1]
RIG_PLAN = os.environ.get("AXM_RIG_PLAN")
WEIGHTING_PROFILE = os.environ.get("AXM_WEIGHTING_PROFILE")


@unittest.skipUnless(RIG_PLAN and WEIGHTING_PROFILE, "exact Rigging donor paths are required")
class BilateralMirrorSurfaceRiggingRebindTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text(encoding="utf-8"))
        cls.left_profile = json.loads((ROOT / "examples/quadruped_elbow_source_successor_003.json").read_text(encoding="utf-8"))
        cls.bilateral_profile = json.loads((ROOT / "examples/quadruped_elbow_bilateral_successor_003.json").read_text(encoding="utf-8"))
        cls.plan = json.loads(Path(RIG_PLAN).read_text(encoding="utf-8"))
        cls.weighting_profile = json.loads(Path(WEIGHTING_PROFILE).read_text(encoding="utf-8"))
        cls.receipt = inspect_bilateral_mirror_surface_rigging_rebind(
            cls.spec,
            cls.left_profile,
            cls.bilateral_profile,
            cls.plan,
            cls.weighting_profile,
        )

    def test_dense_rebind_passes(self):
        self.assertEqual(self.receipt["state"], PASS_STATE)
        self.assertEqual(self.receipt["total_dense_pose_observations"], 484)
        for side in ("left", "right"):
            self.assertEqual(
                self.receipt[side]["baseline_summary"]["gate"],
                "PASS_BILATERAL_SIDE_DENSE_STRUCTURAL_SWEEP",
            )
            self.assertEqual(
                self.receipt[side]["refined_summary"]["gate"],
                "PASS_BILATERAL_SIDE_DENSE_STRUCTURAL_SWEEP",
            )
            self.assertEqual(
                self.receipt[side]["boundary_weighting_comparison"]["gate"],
                "PASS_WEIGHTING_REFINEMENT_RECONFIRMED_ON_BILATERAL_SUCCESSOR",
            )

    def test_exact_surface_metric_mirror_hold_is_closed(self):
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
            row = self.receipt["bilateral_mirror_evidence"][weighting]
            self.assertEqual(row["gate"], "PASS_EXACT_MIRRORED_VERTEX_AND_SURFACE_METRICS")
            self.assertLessEqual(row["maximum_mirrored_pose_residual_m"], MIRROR_TOLERANCE)
            self.assertLessEqual(row["maximum_structural_metric_residual"], MIRROR_TOLERANCE)

    def test_truth_boundary_does_not_claim_animation_or_runtime(self):
        truth = self.receipt["truth_boundary"]
        self.assertFalse(truth["animation_accepted"])
        self.assertFalse(truth["runtime_or_controller_accepted"])
        self.assertFalse(truth["source_or_topology_modified_by_rigging"])
        self.assertFalse(truth["rig_or_weights_modified"])


if __name__ == "__main__":
    unittest.main()
