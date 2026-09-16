import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.topology_study import build_connected_chain, derive_shared_ring_radii


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


if __name__ == "__main__":
    unittest.main()
