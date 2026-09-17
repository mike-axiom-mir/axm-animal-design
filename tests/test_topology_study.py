import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.topology_study import (
    build_connected_chain,
    derive_shared_ring_radii,
    inspect_vertex_fan_connectivity,
)


class ConnectedChainTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT / "examples" / "quadruped_neutral_001.json").read_text())
        self.region_ids = ("front_upper_L", "front_lower_L", "front_paw_L")
        self.radius_derivation = derive_shared_ring_radii(self.spec["regions"], self.region_ids)
        lm = self.spec["landmarks"]
        self.points = [lm[name] for name in self.radius_derivation["path_landmarks"]]
        self.radii = self.radius_derivation["radii_m"]

    def test_source_region_radii_are_derived_not_hand_authored(self):
        self.assertEqual(
            self.radius_derivation["path_landmarks"],
            ["shoulder_L", "elbow_L", "wrist_L", "front_paw_L"],
        )
        self.assertEqual(self.radius_derivation["radii_m"], [0.115, 0.09, 0.07, 0.095])
        self.assertEqual(
            self.radius_derivation["policy"],
            "preserve-endpoints_mean-adjacent-junction-radii",
        )
        elbow, wrist = self.radius_derivation["junctions"]
        self.assertEqual(elbow["incoming_radius_m"], 0.09)
        self.assertEqual(elbow["outgoing_radius_m"], 0.09)
        self.assertEqual(elbow["shared_ring_radius_m"], 0.09)
        self.assertEqual(elbow["authored_radius_gap_m"], 0.0)
        self.assertEqual(wrist["incoming_radius_m"], 0.065)
        self.assertEqual(wrist["outgoing_radius_m"], 0.075)
        self.assertAlmostEqual(wrist["shared_ring_radius_m"], 0.07, places=12)
        self.assertAlmostEqual(wrist["authored_radius_gap_m"], 0.01, places=12)

    def test_radius_derivation_fails_closed_on_invalid_source_chain(self):
        with self.assertRaises(ValueError):
            derive_shared_ring_radii(self.spec["regions"], ("front_upper_L", "rear_lower_L"))
        with self.assertRaises(ValueError):
            derive_shared_ring_radii(self.spec["regions"], ("missing-region",))
        with self.assertRaises(ValueError):
            derive_shared_ring_radii(self.spec["regions"], ("torso",))

    def test_connected_chain_is_deterministic_and_bounded(self):
        first = build_connected_chain("front-left-connected", self.points, self.radii)
        second = build_connected_chain("front-left-connected", self.points, self.radii)
        self.assertEqual(first, second)
        self.assertEqual(first["radii"], self.radius_derivation["radii_m"])
        self.assertEqual(len(first["positions"]), 42)
        self.assertEqual(len(first["indices"]) // 3, 80)
        self.assertTrue(all(0 <= index < len(first["positions"]) for index in first["indices"]))

    def test_connected_chain_has_one_indexed_fan_per_vertex(self):
        mesh = build_connected_chain("front-left-connected", self.points, self.radii)
        report = inspect_vertex_fan_connectivity(mesh["positions"], mesh["indices"])
        self.assertEqual(report["status"], "PASS_CONNECTED_VERTEX_FANS")
        self.assertEqual(report["isolated_vertex_count"], 0)
        self.assertEqual(report["disconnected_vertex_fan_count"], 0)
        self.assertEqual(report["max_vertex_fan_components"], 1)
        self.assertTrue(report["truth_boundary"]["indexed_vertex_fan_connectivity_checked"])
        self.assertFalse(report["truth_boundary"]["self_intersection_checked"])

    def test_vertex_fan_diagnostic_catches_bow_tie_vertex(self):
        positions = [
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1],
            [-1, 0, 0],
            [0, -1, 0],
            [0, 0, -1],
        ]
        indices = [
            0, 2, 1,
            0, 1, 3,
            1, 2, 3,
            2, 0, 3,
            0, 4, 5,
            0, 6, 4,
            4, 6, 5,
            5, 6, 0,
        ]
        report = inspect_vertex_fan_connectivity(positions, indices)
        self.assertEqual(report["status"], "DISCONNECTED_OR_ISOLATED_VERTEX_FANS")
        self.assertEqual(report["isolated_vertex_count"], 0)
        self.assertEqual(report["disconnected_vertex_fan_count"], 1)
        self.assertEqual(report["max_vertex_fan_components"], 2)
        self.assertEqual(report["examples"]["disconnected_vertex_fans"][0]["vertex"], 0)
        self.assertEqual(report["examples"]["disconnected_vertex_fans"][0]["fan_component_count"], 2)

    def test_every_triangle_has_nonzero_area(self):
        mesh = build_connected_chain("front-left-connected", self.points, self.radii)
        positions = mesh["positions"]
        for offset in range(0, len(mesh["indices"]), 3):
            ia, ib, ic = mesh["indices"][offset:offset + 3]
            a, b, c = positions[ia], positions[ib], positions[ic]
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            cross = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            self.assertGreater(sum(value * value for value in cross), 1e-16)

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            build_connected_chain("x", [[0, 0, 0]], [0.1])
        with self.assertRaises(ValueError):
            build_connected_chain("x", [[0, 0, 0], [0, 0, 0]], [0.1, 0.1])
        with self.assertRaises(ValueError):
            build_connected_chain("x", [[0, 0, 0], [1, 0, 0]], [0.1, -0.1])
        with self.assertRaises(ValueError):
            build_connected_chain("x", [[0, 0, 0], [1, 0, 0]], [0.1, 0.1], segments=5)
        with self.assertRaises(ValueError):
            inspect_vertex_fan_connectivity([[0, 0, 0]], [0, 0, 0])
        with self.assertRaises(ValueError):
            inspect_vertex_fan_connectivity([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [0, 1])


if __name__ == "__main__":
    unittest.main()
