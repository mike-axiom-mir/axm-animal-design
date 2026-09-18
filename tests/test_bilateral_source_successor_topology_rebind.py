import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.bilateral_source_successor_topology_rebind import (
    EXPECTED_MOVED_VERTICES,
    build_bilateral_source_successor_topology_rebind,
)


class BilateralSourceSuccessorTopologyRebindTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT / "examples" / "quadruped_neutral_001.json").read_text())
        self.left_profile = json.loads((ROOT / "examples" / "quadruped_elbow_source_successor_003.json").read_text())
        self.bilateral_profile = json.loads((ROOT / "examples" / "quadruped_elbow_bilateral_successor_003.json").read_text())

    def test_exact_bilateral_source_successors_rebind_locally(self):
        left, right, record = build_bilateral_source_successor_topology_rebind(
            self.spec, self.left_profile, self.bilateral_profile
        )
        self.assertEqual(record["state"], "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND")
        self.assertEqual(record["left"]["state"], "PASS_SIDE_LOCAL_TOPOLOGY_REBIND")
        self.assertEqual(record["right"]["state"], "PASS_SIDE_LOCAL_TOPOLOGY_REBIND")
        self.assertEqual(record["left"]["moved_vertex_indices"], EXPECTED_MOVED_VERTICES)
        self.assertEqual(record["right"]["moved_vertex_indices"], EXPECTED_MOVED_VERTICES)
        self.assertEqual(record["left"]["vertex_count"], 42)
        self.assertEqual(record["right"]["vertex_count"], 42)
        self.assertEqual(record["left"]["triangle_count"], 80)
        self.assertEqual(record["right"]["triangle_count"], 80)
        self.assertEqual(
            record["left"]["successor_topology_signature"],
            record["right"]["successor_topology_signature"],
        )
        self.assertEqual(record["left"]["static_self_intersections"]["self_intersection_pair_count"], 0)
        self.assertEqual(record["right"]["static_self_intersections"]["self_intersection_pair_count"], 0)
        self.assertEqual(record["left"]["vertex_fans"]["disconnected_vertex_fan_count"], 0)
        self.assertEqual(record["right"]["vertex_fans"]["disconnected_vertex_fan_count"], 0)
        self.assertTrue(all(v == "PASS" for v in record["bilateral_gates"].values()))
        self.assertFalse(record["truth_boundary"]["right_geometry_pass_inferred_from_symmetry"])
        self.assertEqual(len(left["indices"]), 240)
        self.assertEqual(len(right["indices"]), 240)

    def test_bilateral_profile_identity_drift_fails_closed(self):
        drifted = copy.deepcopy(self.bilateral_profile)
        drifted["right_form_change"]["joint_axis_width_scale"] = 1.031
        with self.assertRaisesRegex(ValueError, "profile identity drift"):
            build_bilateral_source_successor_topology_rebind(
                self.spec, self.left_profile, drifted
            )


if __name__ == "__main__":
    unittest.main()
