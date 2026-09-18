import math
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.animation_reconstruction_temporal_audit import (
    HOLD_STATE,
    PASS_STATE,
    build_temporal_spike_negative_control,
    inspect_reconstruction_temporal_stability,
)


def _synthetic_receipt():
    rows = []
    for index in range(41):
        phase = index / 40.0
        angle = 9.0 * (1.0 - math.cos(2.0 * math.pi * phase))
        envelope = math.sin(math.pi * phase) ** 2
        rows.append(
            {
                "sample_index": index,
                "time_seconds": index / 40.0,
                "angle_deg_from_transport_quaternion": angle,
                "maximum_position_residual_m": 3.7e-8 + 1.0e-12 * envelope,
                "maximum_normal_angle_deg": 2.0e-5 + 1.0e-9 * envelope,
                "maximum_tangent_angle_deg": 3.0e-5 + 1.0e-9 * envelope,
                "maximum_normal_tangent_dot_abs": 5.0e-16 * envelope,
                "split_position_residual_m": 0.0,
                "handedness_mismatch_count": 0,
            }
        )
    return {
        "schema": "axm.animal-post-skin-owner-frame-reconstruction/v0.1",
        "state": "PASS_TRANSPORTED_POST_SKIN_OWNER_FRAME_RECONSTRUCTION_41_KEYS",
        "reconstruction": {
            "gate": "PASS",
            "method": "REBUILD_SOURCE_POSE_FROM_TRANSPORTED_SKINNED_POSITIONS_THEN_REDERIVE_GEOMETRY_OWNER_FRAME",
            "maximum_owner_position_residual_m": 3.8e-8,
            "maximum_owner_normal_angle_deg": 2.1e-5,
            "maximum_owner_tangent_angle_deg": 3.1e-5,
        },
        "truth_boundary": {
            "technical_art_adopted_reconstruction": False,
            "animation_modified": False,
        },
        "all_41_key_samples": rows,
    }


class AnimationReconstructionTemporalAuditTests(unittest.TestCase):
    def test_symmetric_loop_is_temporally_stable(self):
        report = inspect_reconstruction_temporal_stability(_synthetic_receipt())
        self.assertEqual(report["gate"], PASS_STATE)
        self.assertEqual(report["sample_count"], 41)
        self.assertTrue(report["timing"]["pass"])
        self.assertTrue(report["motion_identity"]["pass"])
        temporal = report["reconstruction_error_temporal"]
        self.assertTrue(temporal["mirror_pass"])
        self.assertTrue(temporal["adjacent_stability_pass"])
        self.assertTrue(temporal["loop_error_closure_pass"])
        self.assertTrue(temporal["handedness_zero_all_samples"])

    def test_peak_and_mirror_identity_are_preserved(self):
        report = inspect_reconstruction_temporal_stability(_synthetic_receipt())
        self.assertEqual(report["motion_identity"]["peak_index"], 20)
        self.assertAlmostEqual(report["motion_identity"]["peak_angle_deg"], 18.0)
        self.assertLessEqual(report["motion_identity"]["maximum_angle_mirror_residual_deg"], 1e-12)
        mirrors = report["reconstruction_error_temporal"]["maximum_mirror_residual_by_field"]
        self.assertTrue(all(value <= 1e-12 for value in mirrors.values()))

    def test_sub_rigging_tolerance_asymmetric_spike_fails_closed(self):
        report = build_temporal_spike_negative_control(_synthetic_receipt())
        self.assertEqual(report["gate"], HOLD_STATE)
        temporal = report["reconstruction_error_temporal"]
        self.assertFalse(temporal["mirror_pass"])
        self.assertFalse(temporal["adjacent_stability_pass"])

    def test_non_adoption_truth_boundary_is_required(self):
        receipt = _synthetic_receipt()
        receipt["truth_boundary"]["technical_art_adopted_reconstruction"] = True
        with self.assertRaisesRegex(ValueError, "Technical Art non-adoption"):
            inspect_reconstruction_temporal_stability(receipt)


if __name__ == "__main__":
    unittest.main()
