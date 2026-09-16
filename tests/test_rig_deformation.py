import copy
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.rig_deformation import inspect_rig_deformation

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
PLAN = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())


class RigDeformationTests(unittest.TestCase):
    def test_probe_is_deterministic_and_samples_all_declared_joints(self):
        first = inspect_rig_deformation(SPEC, PLAN)
        second = inspect_rig_deformation(SPEC, PLAN)
        self.assertEqual(first, second)
        self.assertEqual(first["gate"], "PASS")
        self.assertEqual(first["joint_count"], 4)
        self.assertEqual(first["pose_count"], 12)
        self.assertEqual(first["declared_downstream_region_count"], 4)

    def test_weights_pose_invariants_and_downstream_chain_are_retained(self):
        report = inspect_rig_deformation(SPEC, PLAN)
        for joint in report["joints"]:
            self.assertEqual(joint["status"], "PASS")
            self.assertLessEqual(joint["max_weight_sum_error"], 1e-12)
            self.assertGreater(joint["weight_counts"]["blended"], 0)
            self.assertGreater(joint["weight_counts"]["rigid"], 0)
            self.assertEqual(len(joint["downstream_regions"]), 1)
            self.assertEqual(len(joint["articulated_region_chain"]), 2)
            for pose in joint["poses"]:
                self.assertEqual(pose["status"], "PASS")
                self.assertEqual(pose["collapsed_triangles"], 0)
                self.assertLessEqual(pose["fixed_weight_vertex_max_drift"], 1e-9)
                self.assertLessEqual(pose["rigid_weight_radius_max_drift"], 1e-9)
                self.assertGreater(pose["minimum_triangle_area_ratio"], 0.0)
                self.assertGreater(pose["minimum_edge_length_ratio"], 0.0)
                self.assertEqual(len(pose["downstream_regions"]), 1)
                self.assertEqual(pose["downstream_regions"][0]["status"], "PASS")
                self.assertEqual(len(pose["chain_continuity"]), 1)
                continuity = pose["chain_continuity"][0]
                self.assertEqual(continuity["status"], "PASS")
                self.assertLessEqual(continuity["absolute_gap_drift"], continuity["tolerance"])

    def test_nonzero_poses_move_paw_with_lower_limb_without_gap_growth(self):
        report = inspect_rig_deformation(SPEC, PLAN)
        for joint in report["joints"]:
            nonzero = [pose for pose in joint["poses"] if pose["angle_deg"] != 0.0]
            self.assertEqual(len(nonzero), 2)
            for pose in nonzero:
                continuity = pose["chain_continuity"][0]
                self.assertAlmostEqual(
                    continuity["source_minimum_vertex_gap"],
                    continuity["posed_minimum_vertex_gap"],
                    places=9,
                )
                downstream = pose["downstream_regions"][0]
                self.assertAlmostEqual(downstream["minimum_edge_length_ratio"], 1.0, places=9)
                self.assertAlmostEqual(downstream["maximum_edge_length_ratio"], 1.0, places=9)

    def test_probe_cannot_exceed_declared_bend_reserve(self):
        changed = copy.deepcopy(PLAN)
        changed["joints"][0]["influence_radius"] = 0.111
        with self.assertRaisesRegex(ValueError, "exceeds declared bend reserve"):
            inspect_rig_deformation(SPEC, changed)

    def test_probe_rejects_undeclared_mesh_region(self):
        changed = copy.deepcopy(PLAN)
        changed["joints"][0]["child_region"] = "invented-limb"
        with self.assertRaisesRegex(ValueError, "unknown mesh regions"):
            inspect_rig_deformation(SPEC, changed)

    def test_probe_rejects_unknown_downstream_region(self):
        changed = copy.deepcopy(PLAN)
        changed["joints"][0]["downstream_regions"] = ["invented-paw"]
        with self.assertRaisesRegex(ValueError, "unknown downstream mesh region"):
            inspect_rig_deformation(SPEC, changed)

    def test_probe_rejects_duplicate_downstream_region(self):
        changed = copy.deepcopy(PLAN)
        changed["joints"][0]["downstream_regions"] = ["front_lower_L"]
        with self.assertRaisesRegex(ValueError, "must be unique and exclude parent/child regions"):
            inspect_rig_deformation(SPEC, changed)

    def test_probe_rejects_unbounded_pose_angle(self):
        changed = copy.deepcopy(PLAN)
        changed["joints"][0]["pose_angles_deg"] = [121]
        with self.assertRaisesRegex(ValueError, "exceeds bounded probe range"):
            inspect_rig_deformation(SPEC, changed)


if __name__ == "__main__":
    unittest.main()
