import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.animation_playback import (
    _build_display_schedule,
    inspect_sampled_playback,
    playback_frame_index,
)

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
PLAN = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())
CLIP = json.loads((ROOT / "examples/quadruped_articulation_loop_001.json").read_text())


class AnimationPlaybackTests(unittest.TestCase):
    def test_exact_clip_has_clean_discrete_playback_seam(self):
        report = inspect_sampled_playback(SPEC, PLAN, CLIP)
        self.assertEqual(report["gate"], "PASS_DISCRETE_SAMPLED_PLAYBACK_SEAM")
        self.assertEqual(report["playback_mode"], "DISCRETE_AUTHORED_SAMPLES_NO_INTERPOLATION")
        self.assertEqual(report["endpoint_inclusive_source_sample_count"], 41)
        self.assertEqual(report["displayed_frame_count_per_cycle"], 40)
        self.assertEqual(report["display_frame_interval_seconds"], 0.025)
        self.assertEqual(report["display_schedule_seconds"][0], 0.0)
        self.assertEqual(report["display_schedule_seconds"][-1], 0.975)
        self.assertTrue(report["metrics"]["exact_endpoint_seam"])
        self.assertTrue(report["metrics"]["index_probe_pass"])
        self.assertLessEqual(
            report["metrics"]["wrap_step_residual_m"],
            report["metrics"]["position_tolerance_m"],
        )

    def test_playback_index_wraps_exact_boundaries_to_neutral(self):
        self.assertEqual(playback_frame_index(0.0, 1.0, 40), 0)
        self.assertEqual(playback_frame_index(0.024999, 1.0, 40), 0)
        self.assertEqual(playback_frame_index(0.025, 1.0, 40), 1)
        self.assertEqual(playback_frame_index(0.999999999, 1.0, 40), 39)
        self.assertEqual(playback_frame_index(1.0, 1.0, 40), 0)
        self.assertEqual(playback_frame_index(1.025, 1.0, 40), 1)
        self.assertEqual(playback_frame_index(2.0, 1.0, 40), 0)

    def test_schedule_rejects_wrong_endpoint_inclusive_count(self):
        with self.assertRaisesRegex(ValueError, "endpoint-inclusive"):
            _build_display_schedule(1.0, 40, 40)

    def test_negative_time_is_not_silently_wrapped(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            playback_frame_index(-0.001, 1.0, 40)

    def test_source_validation_still_fails_closed(self):
        bad = copy.deepcopy(CLIP)
        bad["retained_keyframe_times_seconds"][-1] = 0.975
        with self.assertRaisesRegex(ValueError, "exact clip start and end"):
            inspect_sampled_playback(SPEC, PLAN, bad)


if __name__ == "__main__":
    unittest.main()
