import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.connected_weighting_refinement import (
    EXPECTED_PROFILE_DIGEST,
    inspect_connected_weighting_refinement,
)
from axm_animal_design.connected_deformation import CANDIDATE_DIGEST, digest

SOURCE = json.loads((ROOT / "examples" / "quadruped_neutral_001.json").read_text(encoding="utf-8"))


def plan_fixture():
    return {
        "schema": "axm.animal-rig-deformation-plan/v0.1",
        "name": "quadruped-neutral-001-rig-probe",
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


def profile_fixture(plan):
    return {
        "schema": "axm.animal-weighting-refinement/v0.1",
        "name": "quadruped-weighting-refinement-001",
        "source_name": "quadruped-neutral-001",
        "baseline_plan_digest": digest(plan),
        "baseline_profile": "smoothstep-v0",
        "candidate_profile": "ease-out-power-0p75-v1",
        "candidate_exponent": 0.75,
        "scope": "Same exact source, joints, axes, influence radii, downstream inheritance and -60/0/+60 pose samples; candidate changes only child-region weight falloff.",
    }


class ConnectedWeightingRefinementTests(unittest.TestCase):
    def test_exact_connected_topology_candidate_passes_comparison(self):
        plan = plan_fixture()
        profile = profile_fixture(plan)
        self.assertEqual(digest(profile), EXPECTED_PROFILE_DIGEST)
        receipt = inspect_connected_weighting_refinement(SOURCE, plan, profile)
        self.assertEqual(receipt["connected_candidate_digest"], CANDIDATE_DIGEST)
        self.assertEqual(receipt["baseline_weighting"], "smoothstep-v0")
        self.assertEqual(receipt["candidate_weighting"], "ease-out-power-0p75-v1")
        self.assertEqual(receipt["weight_counts"], {"fixed": 16, "blended": 5, "rigid": 21})
        self.assertEqual(receipt["gate"], "PASS_CONNECTED_TOPOLOGY_WEIGHTING_REFINEMENT")

        by_angle = {row["angle_deg"]: row for row in receipt["comparisons"]}
        negative = by_angle[-60.0]
        self.assertEqual(negative["comparison"], "PASS_NONWORSE_WITH_STRICT_IMPROVEMENT")
        self.assertEqual(negative["baseline_minimum_triangle_area_ratio"], 0.404056348)
        self.assertEqual(negative["candidate_minimum_triangle_area_ratio"], 0.470061418)
        self.assertEqual(negative["baseline_minimum_edge_length_ratio"], 0.773457548)
        self.assertEqual(negative["candidate_minimum_edge_length_ratio"], 0.79173101)

        neutral = by_angle[0.0]
        self.assertEqual(neutral["comparison"], "PASS_NEUTRAL_IDENTICAL")
        self.assertEqual(neutral["maximum_baseline_to_candidate_vertex_delta_m"], 0.0)

        positive = by_angle[60.0]
        self.assertEqual(positive["comparison"], "PASS_NONWORSE_WITH_STRICT_IMPROVEMENT")
        self.assertEqual(positive["baseline_maximum_triangle_area_ratio"], 1.241793395)
        self.assertEqual(positive["candidate_maximum_triangle_area_ratio"], 1.220796683)
        self.assertEqual(positive["baseline_maximum_edge_length_ratio"], 1.240197116)
        self.assertEqual(positive["candidate_maximum_edge_length_ratio"], 1.219304492)
        self.assertEqual(negative["candidate_self_intersections"], 0)
        self.assertEqual(positive["candidate_self_intersections"], 0)

    def test_rejects_weighting_profile_identity_drift(self):
        plan = plan_fixture()
        profile = profile_fixture(plan)
        profile["candidate_exponent"] = 0.74
        with self.assertRaisesRegex(ValueError, "candidate exponent drift"):
            inspect_connected_weighting_refinement(SOURCE, plan, profile)

    def test_rejects_weighting_profile_plan_drift(self):
        plan = plan_fixture()
        profile = profile_fixture(plan)
        profile["baseline_plan_digest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "rig-plan identity mismatch"):
            inspect_connected_weighting_refinement(SOURCE, plan, profile)

    def test_rejects_connected_topology_source_drift(self):
        plan = plan_fixture()
        profile = profile_fixture(plan)
        source = copy.deepcopy(SOURCE)
        for region in source["regions"]:
            if region.get("id") == "front_paw_L":
                region["radius_a"] = 0.076
                break
        with self.assertRaisesRegex(ValueError, "connected candidate identity drift"):
            inspect_connected_weighting_refinement(source, plan, profile)


if __name__ == "__main__":
    unittest.main()
