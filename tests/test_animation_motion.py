import copy
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.animation_motion import build_animation_frame, inspect_animation_motion

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
PLAN = json.loads((ROOT / "examples/quadruped_rig_probe_001.json").read_text())
CLIP = json.loads((ROOT / "examples/quadruped_articulation_loop_001.json").read_text())


class AnimationMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = inspect_animation_motion(SPEC, PLAN, CLIP)

    def test_loop_is_deterministic_nonzero_and_exactly_returns_to_neutral(self):
        self.assertEqual(self.report, inspect_animation_motion(SPEC, PLAN, CLIP))
        self.assertEqual(self.report["gate"], "PASS")
        self.assertEqual(self.report["sample_count"], 41)
        self.assertEqual(self.report["track_count"], 4)
        self.assertEqual(self.report["rig_weighting_profile"], "smoothstep-v0")
        self.assertTrue(self.report["metrics"]["exact_neutral_start"])
        self.assertTrue(self.report["metrics"]["exact_neutral_return"])
        self.assertGreater(self.report["metrics"]["distinct_surface_count"], 2)
        for length in self.report["metrics"]["distal_marker_path_lengths_m"].values():
            self.assertGreater(length, 0.01)

    def test_every_sample_reuses_repaired_chain_propagation(self):
        self.assertLessEqual(
            self.report["metrics"]["maximum_chain_gap_drift_m"],
            self.report["metrics"]["chain_gap_tolerance_m"],
        )
        for sample in self.report["sampled_motion"]:
            self.assertEqual(sample["status"], "PASS")
            for joint in sample["joints"].values():
                self.assertEqual(joint["status"], "PASS")
                self.assertEqual(joint["collapsed_triangles"], 0)
                self.assertGreater(joint["minimum_triangle_area_ratio"], 0.0)
                for continuity in joint["chain_continuity"]:
                    self.assertEqual(continuity["status"], "PASS")
                    self.assertLessEqual(continuity["absolute_gap_drift"], continuity["tolerance"])

    def test_peak_sample_matches_bounded_authored_angles_and_bilateral_pairs(self):
        peak = self.report["sampled_motion"][20]
        self.assertEqual(peak["time_seconds"], 0.5)
        self.assertEqual(peak["angles_deg"]["front-elbow-L"], 18.0)
        self.assertEqual(peak["angles_deg"]["front-elbow-R"], 18.0)
        self.assertEqual(peak["angles_deg"]["hind-knee-L"], 14.0)
        self.assertEqual(peak["angles_deg"]["hind-knee-R"], 14.0)
        self.assertTrue(self.report["metrics"]["bilateral_peak_angle_match"])

    def test_retained_keyframes_are_real_sampled_surfaces(self):
        times = [0.0, 0.25, 0.5, 0.75, 1.0]
        self.assertEqual([row["time_seconds"] for row in self.report["retained_keyframes"]], times)
        for time_seconds in times:
            frame = build_animation_frame(SPEC, PLAN, CLIP, time_seconds)
            self.assertEqual(frame["surface_digest"], next(
                row["surface_digest"]
                for row in self.report["sampled_motion"]
                if row["time_seconds"] == time_seconds
            ))

        changed = copy.deepcopy(CLIP)
        changed["retained_keyframe_times_seconds"] = [0.0, 0.2375, 0.5, 0.75, 1.0]
        with self.assertRaisesRegex(ValueError, "must land on sampled frames"):
            inspect_animation_motion(SPEC, PLAN, changed)

    def test_clip_rejects_motion_outside_rig_probed_envelope(self):
        changed = copy.deepcopy(CLIP)
        changed["tracks"][0]["peak_angle_deg"] = 61.0
        with self.assertRaisesRegex(ValueError, "exceeds rig-probed angle envelope"):
            inspect_animation_motion(SPEC, PLAN, changed)

    def test_clip_rejects_unknown_joint_source_drift_and_weighting_relabel(self):
        changed = copy.deepcopy(CLIP)
        changed["tracks"][0]["joint_id"] = "invented-joint"
        with self.assertRaisesRegex(ValueError, "unknown rig joint"):
            inspect_animation_motion(SPEC, PLAN, changed)

        changed = copy.deepcopy(CLIP)
        changed["source_name"] = "other-source"
        with self.assertRaisesRegex(ValueError, "source_name must match"):
            inspect_animation_motion(SPEC, PLAN, changed)

        changed = copy.deepcopy(CLIP)
        changed["rig_weighting_profile"] = "ease-out-power-0p75-v1"
        with self.assertRaisesRegex(ValueError, "smoothstep-v0"):
            inspect_animation_motion(SPEC, PLAN, changed)

    def test_truth_label_cannot_be_silently_promoted_to_gait(self):
        changed = copy.deepcopy(CLIP)
        changed["motion_semantics"] = "GAIT"
        with self.assertRaisesRegex(ValueError, "bounded non-locomotion truth label"):
            inspect_animation_motion(SPEC, PLAN, changed)


if __name__ == "__main__":
    unittest.main()
