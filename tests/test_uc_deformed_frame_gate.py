import copy
import unittest

from axm_animal_design.uc_deformed_frame_gate import (
    FAIL_STATE,
    HOLD_STATE,
    PASS_STATE,
    RIGGING_HOLD_STATE,
    RIGGING_PASS_STATE,
    evaluate_deformed_direction_frame_gate,
    require_tangent_space_runtime_ready,
)


TA_HEAD = "4649d144841fbd1f3f43e9c7deb6f37b91fbd93d"
GLB_SHA = "ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493"
RIG_HEAD = "fdfeb0e32d8b51107e9bd648210a1eaf8aaf7f3e"
UC_HEAD = "eb571ebd67b0e6c82387f1da32700e9be844b2af"
UC_BLOB = "b1f2e68bb6c6800af5496decc95a8044d141edc9"


def receipt(state=RIGGING_HOLD_STATE):
    return {
        "schema": "axm.animal-transported-tangent-deformation-audit/v0.1",
        "state": state,
        "technical_art": {"head": TA_HEAD, "glb_sha256": GLB_SHA},
        "position_uv_handedness": {
            "gate": "PASS",
            "maximum_position_residual_m": 3.712575483167813e-08,
            "maximum_uv_residual": 2.6656007523325565e-08,
            "tangent_handedness_mismatch_count": 0,
        },
        "direction_frames": {
            "normal_deformation_excess_deg": 7.541933278181338,
            "corrected_tangent_deformation_excess_deg": 3.6840862372161047,
            "maximum_corrected_normal_tangent_dot_abs": 1.6653345369377348e-16,
            "post_skin_gram_schmidt_orthogonality_gate": "PASS",
        },
        "truth_boundary": {
            "position_equivalence_established": True,
            "deformed_direction_frame_equivalence_established": state == RIGGING_PASS_STATE,
        },
    }


class DeformedFrameGateTests(unittest.TestCase):
    def evaluate(self, value):
        return evaluate_deformed_direction_frame_gate(
            value,
            expected_technical_art_head=TA_HEAD,
            expected_glb_sha256=GLB_SHA,
            exact_rigging_head=RIG_HEAD,
            current_uc_head=UC_HEAD,
            current_uc_codec_blob=UC_BLOB,
        )

    def test_exact_rigging_hold_stays_hold_despite_position_and_orthogonality_pass(self):
        decision = self.evaluate(receipt())
        self.assertEqual(decision["state"], HOLD_STATE)
        self.assertEqual(decision["capabilities"]["position_uv_handedness"], "PASS")
        self.assertEqual(decision["capabilities"]["post_skin_gram_schmidt_orthogonality"], "PASS")
        self.assertEqual(decision["capabilities"]["deformed_direction_frame"], "HOLD")
        self.assertFalse(decision["capabilities"]["tangent_space_runtime_ready"])
        with self.assertRaisesRegex(ValueError, "promotion refused"):
            require_tangent_space_runtime_ready(decision)

    def test_future_owner_pass_can_promote_only_when_measured_excess_is_within_gate(self):
        value = receipt(RIGGING_PASS_STATE)
        value["direction_frames"]["normal_deformation_excess_deg"] = 5e-7
        value["direction_frames"]["corrected_tangent_deformation_excess_deg"] = 5e-7
        decision = self.evaluate(value)
        self.assertEqual(decision["state"], PASS_STATE)
        self.assertTrue(decision["capabilities"]["tangent_space_runtime_ready"])
        require_tangent_space_runtime_ready(decision)

    def test_position_failure_is_not_downgraded_to_direction_hold(self):
        value = receipt()
        value["position_uv_handedness"]["maximum_position_residual_m"] = 0.001
        value["truth_boundary"]["position_equivalence_established"] = False
        self.assertEqual(self.evaluate(value)["state"], FAIL_STATE)

    def test_exact_technical_art_identity_drift_fails_closed(self):
        value = copy.deepcopy(receipt())
        value["technical_art"]["glb_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "GLB identity drift"):
            self.evaluate(value)

    def test_owner_truth_cannot_claim_direction_pass_over_hold_measurements(self):
        value = receipt()
        value["truth_boundary"]["deformed_direction_frame_equivalence_established"] = True
        with self.assertRaisesRegex(ValueError, "truth boundary contradicts"):
            self.evaluate(value)


if __name__ == "__main__":
    unittest.main()
