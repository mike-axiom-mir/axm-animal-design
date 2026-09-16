import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.source_successor_topology_rebind import (
    EXPECTED_MOVED_VERTICES,
    build_source_successor_topology_rebind,
)


class SourceSuccessorTopologyRebindTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT / "examples" / "quadruped_neutral_001.json").read_text())
        self.profile = json.loads((ROOT / "examples" / "quadruped_elbow_source_successor_003.json").read_text())

    def test_exact_source_successor_rebind_passes_local_geometry_gates(self):
        candidate, record = build_source_successor_topology_rebind(self.spec, self.profile)
        self.assertEqual(record["state"], "PASS_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND")
        self.assertEqual(record["vertex_count"], 42)
        self.assertEqual(record["triangle_count"], 80)
        self.assertEqual(record["moved_vertex_indices"], EXPECTED_MOVED_VERTICES)
        self.assertEqual(record["baseline_topology_signature"], record["successor_topology_signature"])
        self.assertTrue(all(value == "PASS" for value in record["gates"].values()))
        self.assertEqual(record["vertex_fans"]["status"], "PASS_CONNECTED_VERTEX_FANS")
        self.assertEqual(record["static_self_intersections"]["status"], "PASS_NO_NONADJACENT_SELF_INTERSECTIONS")
        self.assertEqual(record["static_self_intersections"]["self_intersection_pair_count"], 0)
        self.assertFalse(record["truth_boundary"]["organic_source_shape_modified"])
        self.assertFalse(record["truth_boundary"]["historical_geometry_pass_silently_inherited"])
        self.assertFalse(record["truth_boundary"]["deformation_retested"])
        self.assertEqual(len(candidate["indices"]), 240)

    def test_profile_identity_drift_fails_closed(self):
        drifted = copy.deepcopy(self.profile)
        drifted["form_change"]["joint_axis_width_scale"] = 1.031
        with self.assertRaisesRegex(ValueError, "profile identity drift"):
            build_source_successor_topology_rebind(self.spec, drifted)


if __name__ == "__main__":
    unittest.main()
