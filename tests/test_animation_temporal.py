import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.animation_temporal import inspect_temporal_continuity

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
PLAN = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())
CLIP = json.loads((ROOT / "examples/quadruped_articulation_loop_001.json").read_text())


class AnimationTemporalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = inspect_temporal_continuity(SPEC, PLAN, CLIP)

    def test_temporal_probe_is_deterministic_and_green(self):
        self.assertEqual(self.report, inspect_temporal_continuity(SPEC, PLAN, CLIP))
        self.assertEqual(self.report["gate"], "PASS_LOOP_TEMPORAL_CONTINUITY")
        self.assertEqual(self.report["sample_count"], 41)
        self.assertEqual(self.report["sample_rate_hz"], 40)
        self.assertEqual(self.report["sample_interval_seconds"], 0.025)
        self.assertEqual(
            self.report["review_sample_times_seconds"],
            [0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0],
        )

    def test_loop_has_exact_neutral_closure_and_stable_sampled_topology(self):
        metrics = self.report["metrics"]
        self.assertTrue(metrics["topology_stable"])
        self.assertTrue(metrics["uniform_sample_times"])
        self.assertTrue(metrics["exact_neutral_start"])
        self.assertTrue(metrics["exact_neutral_return"])
        self.assertLessEqual(metrics["neutral_return_position_residual_m"], 1e-8)
        self.assertTrue(metrics["nonzero_adjacent_motion"])

    def test_time_mirror_and_phase_contract_hold_for_every_track(self):
        metrics = self.report["metrics"]
        self.assertLessEqual(metrics["maximum_time_mirror_position_residual_m"], 1e-8)
        self.assertLessEqual(metrics["maximum_time_mirror_angle_residual_deg"], 1e-8)
        self.assertLessEqual(metrics["maximum_time_mirror_step_residual_m"], 1e-8)
        self.assertTrue(metrics["tracks_phase_clean"])
        for row in self.report["track_phase_checks"].values():
            self.assertTrue(row["monotonic_rise"])
            self.assertTrue(row["monotonic_fall"])
            self.assertTrue(row["peak_at_midpoint"])
            self.assertEqual(row["start_angle_deg"], 0.0)
            self.assertEqual(row["end_angle_deg"], 0.0)
            self.assertGreater(row["peak_angle_deg"], 0.0)

    def test_sampled_geometric_step_stays_bounded_relative_to_peak_excursion(self):
        metrics = self.report["metrics"]
        self.assertGreater(metrics["peak_vertex_excursion_from_neutral_m"], 0.0)
        self.assertGreater(metrics["maximum_adjacent_vertex_step_m"], 0.0)
        self.assertLessEqual(
            metrics["maximum_adjacent_step_fraction_of_peak_excursion"],
            metrics["step_fraction_limit"],
        )
        self.assertEqual(len(self.report["adjacent_max_vertex_steps_m"]), 40)


if __name__ == "__main__":
    unittest.main()
