import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.ring_phase_study import derive_ring_phase_candidate
from axm_animal_design.topology_study import (
    build_connected_chain,
    derive_shared_ring_radii,
    inspect_vertex_fan_connectivity,
)


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class ConnectedChainRingPhaseTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT / "examples" / "quadruped_neutral_001.json").read_text())
        derived = derive_shared_ring_radii(
            self.spec["regions"],
            ("front_upper_L", "front_lower_L", "front_paw_L"),
        )
        landmarks = self.spec["landmarks"]
        self.baseline = build_connected_chain(
            "front-left-connected-chain-001",
            [landmarks[name] for name in derived["path_landmarks"]],
            derived["radii_m"],
            segments=10,
        )

    def test_exact_existing_baseline_identity_is_unchanged(self):
        self.assertEqual(
            _digest(self.baseline),
            "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c",
        )

    def test_phase_candidate_preserves_connectivity_source_path_and_poles(self):
        before = json.loads(json.dumps(self.baseline))
        candidate = derive_ring_phase_candidate(
            self.baseline,
            identifier="front-left-connected-chain-phase-4p5",
            phase_degrees=4.5,
        )
        self.assertEqual(self.baseline, before)
        self.assertNotEqual(candidate["positions"], self.baseline["positions"])
        self.assertEqual(candidate["indices"], self.baseline["indices"])
        self.assertEqual(candidate["path_points"], self.baseline["path_points"])
        self.assertEqual(candidate["radii"], self.baseline["radii"])
        self.assertEqual(candidate["segments"], self.baseline["segments"])
        self.assertEqual(candidate["positions"][0], self.baseline["positions"][0])
        self.assertEqual(candidate["positions"][-1], self.baseline["positions"][-1])
        self.assertEqual(candidate["ring_phase_degrees"], 4.5)
        self.assertEqual(candidate["ring_phase_segment_pitch_degrees"], 36.0)
        fan = inspect_vertex_fan_connectivity(candidate["positions"], candidate["indices"])
        self.assertEqual(fan["status"], "PASS_CONNECTED_VERTEX_FANS")
        self.assertEqual(fan["disconnected_vertex_fan_count"], 0)
        self.assertEqual(fan["isolated_vertex_count"], 0)

    def test_phase_candidate_is_deterministic(self):
        first = derive_ring_phase_candidate(
            self.baseline,
            identifier="front-left-connected-chain-phase-4p5",
            phase_degrees=4.5,
        )
        second = derive_ring_phase_candidate(
            self.baseline,
            identifier="front-left-connected-chain-phase-4p5",
            phase_degrees=4.5,
        )
        self.assertEqual(first, second)
        self.assertNotEqual(_digest(first), _digest(self.baseline))

    def test_invalid_or_unbounded_phase_fails_closed(self):
        for value in (0.0, -1.0, 36.0, 360.0, float("inf"), float("nan"), True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    derive_ring_phase_candidate(
                        self.baseline,
                        identifier="invalid",
                        phase_degrees=value,
                    )

    def test_wrong_mesh_layout_fails_closed(self):
        broken = json.loads(json.dumps(self.baseline))
        broken["positions"].pop()
        with self.assertRaises(ValueError):
            derive_ring_phase_candidate(
                broken,
                identifier="invalid-layout",
                phase_degrees=4.5,
            )


if __name__ == "__main__":
    unittest.main()
