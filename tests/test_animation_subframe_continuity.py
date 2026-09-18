import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.animation_subframe_continuity import (
    inspect_hidden_between_key_negative_control,
    inspect_subframe_continuity,
)

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
PLAN = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())
CLIP = json.loads((ROOT / "examples/quadruped_articulation_loop_001.json").read_text())


class AnimationSubframeContinuityTests(unittest.TestCase):
    def test_exact_source_passes_dense_subframe_witness(self):
        report = inspect_subframe_continuity(SPEC, PLAN, CLIP)
        self.assertEqual(report["gate"], "PASS_DENSE_SUBFRAME_SOURCE_CURVE_CONTINUITY_WITNESS")
        self.assertEqual(report["authored_sample_count"], 41)
        self.assertEqual(report["subframes_per_authored_interval"], 8)
        self.assertEqual(report["dense_sample_rate_hz"], 320)
        self.assertEqual(report["dense_sample_count"], 321)
        metrics = report["metrics"]
        self.assertTrue(metrics["topology_stable"])
        self.assertLessEqual(metrics["maximum_authored_sample_position_rebind_residual_m"], 1e-9)
        self.assertLessEqual(metrics["maximum_authored_sample_angle_rebind_residual_deg"], 1e-9)
        self.assertLessEqual(metrics["loop_position_residual_m"], 1e-9)
        self.assertLessEqual(metrics["loop_angle_residual_deg"], 1e-9)
        self.assertLessEqual(metrics["maximum_time_mirror_position_residual_m"], 1e-9)
        self.assertLessEqual(metrics["maximum_time_mirror_angle_residual_deg"], 1e-9)
        self.assertLessEqual(metrics["maximum_dense_bilateral_angle_residual_deg"], 1e-9)
        self.assertLessEqual(metrics["maximum_start_source_velocity_deg_s"], 1e-9)
        self.assertLessEqual(metrics["maximum_midpoint_source_velocity_deg_s"], 1e-9)
        self.assertLessEqual(metrics["maximum_end_source_velocity_deg_s"], 1e-9)
        self.assertLessEqual(metrics["loop_source_acceleration_residual_deg_s2"], 1e-9)
        self.assertTrue(metrics["monotonic_rise"])
        self.assertTrue(metrics["monotonic_fall"])
        self.assertGreater(metrics["maximum_dense_adjacent_vertex_step_m"], 0.0)
        self.assertLess(metrics["maximum_dense_adjacent_vertex_step_m"], metrics["maximum_authored_adjacent_vertex_step_m"])

    def test_hidden_between_key_bump_is_detected_while_authored_samples_stay_exact(self):
        report = inspect_hidden_between_key_negative_control(SPEC, PLAN, CLIP)
        self.assertEqual(report["gate"], "HOLD_DENSE_SUBFRAME_SOURCE_CURVE_CONTINUITY")
        self.assertTrue(report["negative_control"]["authored_samples_preserved"])
        metrics = report["metrics"]
        self.assertLessEqual(metrics["maximum_authored_sample_position_rebind_residual_m"], 1e-9)
        self.assertLessEqual(metrics["maximum_authored_sample_angle_rebind_residual_deg"], 1e-9)
        self.assertGreater(metrics["maximum_dense_bilateral_angle_residual_deg"], 0.049)
        self.assertGreater(metrics["maximum_time_mirror_angle_residual_deg"], 0.049)
        self.assertGreater(metrics["maximum_time_mirror_position_residual_m"], 1e-6)

    def test_subframe_factor_is_bounded(self):
        with self.assertRaises(ValueError):
            inspect_subframe_continuity(SPEC, PLAN, CLIP, subframes_per_authored_interval=1)
        with self.assertRaises(ValueError):
            inspect_subframe_continuity(SPEC, PLAN, CLIP, subframes_per_authored_interval=33)


if __name__ == "__main__":
    unittest.main()
