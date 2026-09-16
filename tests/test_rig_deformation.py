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

    def test_weights_and_pose_invariants_are_retained(self):
        report = inspect_rig_deformation(SPEC, PLAN)
        for joint in report["joints"]:
            self.assertEqual(joint["status"], "PASS")
            self.assertLessEqual(joint["max_weight_sum_error"], 1e-12)
            self.assertGreater(joint["weight_counts"]["blended"], 0)
            self.assertGreater(joint["weight_counts"]["rigid"], 0)
            for pose in joint["poses"]:
                self.assertEqual(pose["status"], "PASS")
                self.assertEqual(pose["collapsed_triangles"], 0)
                self.assertLessEqual(pose["fixed_weight_vertex_max_drift"], 1e-9)
                self.assertLessEqual(pose["rigid_weight_radius_max_drift"], 1e-9)
                self.assertGreater(pose["minimum_triangle_area_ratio"], 0.0)
                self.assertGreater(pose["minimum_edge_length_ratio"], 0.0)

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

    def test_probe_rejects_unbounded_pose_angle(self):
        changed = copy.deepcopy(PLAN)
        changed["joints"][0]["pose_angles_deg"] = [121]
        with self.assertRaisesRegex(ValueError, "exceeds bounded probe range"):
            inspect_rig_deformation(SPEC, changed)


if __name__ == "__main__":
    unittest.main()
