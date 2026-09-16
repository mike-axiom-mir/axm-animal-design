import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.connected_deformation import (
    CANDIDATE_DIGEST,
    inspect_connected_forelimb_deformation,
)

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


class ConnectedForelimbDeformationTests(unittest.TestCase):
    def test_exact_connected_candidate_passes_bounded_sampled_probe(self):
        receipt = inspect_connected_forelimb_deformation(SOURCE, plan_fixture())
        self.assertEqual(receipt["candidate_digest"], CANDIDATE_DIGEST)
        self.assertEqual(receipt["candidate_vertices"], 42)
        self.assertEqual(receipt["candidate_triangles"], 80)
        self.assertEqual(receipt["joint_id"], "front-elbow-L")
        self.assertEqual(receipt["weighting"], "smoothstep-v0")
        self.assertEqual(receipt["gate"], "PASS_CONNECTED_FORELIMB_BOUNDED_DEFORMATION")
        self.assertEqual([row["angle_deg"] for row in receipt["poses"]], [-60.0, 0.0, 60.0])
        for pose in receipt["poses"]:
            self.assertEqual(pose["status"], "PASS")
            self.assertEqual(pose["collapsed_triangles"], 0)
            self.assertEqual(pose["nonadjacent_self_intersection_pairs"], 0)
        neutral = receipt["poses"][1]
        self.assertEqual(neutral["neutral_max_vertex_drift"], 0.0)

    def test_rejects_rig_axis_drift(self):
        plan = plan_fixture()
        plan["joints"][0]["axis"] = [1.0, 0.0, 0.0]
        with self.assertRaisesRegex(ValueError, "axis drifted"):
            inspect_connected_forelimb_deformation(SOURCE, plan)

    def test_rejects_source_chain_radius_drift(self):
        source = copy.deepcopy(SOURCE)
        for region in source["regions"]:
            if region.get("id") == "front_paw_L":
                region["radius_a"] = 0.076
                break
        with self.assertRaisesRegex(ValueError, "connected candidate identity drift"):
            inspect_connected_forelimb_deformation(source, plan_fixture())

    def test_rejects_missing_exact_joint(self):
        plan = plan_fixture()
        plan["joints"][0]["id"] = "different-joint"
        with self.assertRaisesRegex(ValueError, "exactly one front-elbow-L"):
            inspect_connected_forelimb_deformation(SOURCE, plan)


if __name__ == "__main__":
    unittest.main()
