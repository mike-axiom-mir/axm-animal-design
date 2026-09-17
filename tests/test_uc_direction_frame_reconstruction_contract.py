import copy
import unittest

from axm_animal_design.uc_direction_frame_reconstruction_contract import (
    PASS_STATE,
    adopt_direction_frame_reconstruction_contract,
    require_target_runtime_ready,
)


RIGGING_HEAD = "81ab44eab2e13bed95187610a476be2b2c4667a7"
RIGGING_ARTIFACT_ID = 10476642320
RIGGING_ARTIFACT_SHA256 = "2d11836cc7c1ada5146752d0b6205d0e4f476cd085ee8be4964e2f024f70fa58"
SOURCE_TA_HEAD = "4649d144841fbd1f3f43e9c7deb6f37b91fbd93d"
SOURCE_GLB_SHA256 = "ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493"
CURRENT_TA_HEAD = "test-current-technical-art-head"
CURRENT_UC_HEAD = "test-current-uc-head"
CURRENT_UC_BLOB = "test-current-uc-codec-blob"


def owner_receipt():
    return {
        "schema": "axm.animal-post-skin-owner-frame-reconstruction/v0.1",
        "state": "PASS_TRANSPORTED_POST_SKIN_OWNER_FRAME_RECONSTRUCTION_41_KEYS",
        "premise": {
            "static_direction_transport_gate": "HOLD",
            "static_normal_deformation_excess_deg": 7.541933278181338,
            "static_corrected_tangent_deformation_excess_deg": 3.6840862372161047,
        },
        "motion_boundary": {
            "authored_key_count": 41,
            "time_start_seconds": 0.0,
            "time_end_seconds": 1.0,
        },
        "reconstruction": {
            "gate": "PASS",
            "maximum_uv_split_position_residual_m": 0.0,
            "maximum_owner_position_residual_m": 3.712575483167813e-08,
            "maximum_owner_normal_angle_deg": 2.0081521282065968e-05,
            "maximum_owner_tangent_angle_deg": 3.181419632879438e-05,
            "maximum_normal_tangent_dot_abs": 1.1657341758564144e-15,
            "tangent_handedness_mismatch_count": 0,
        },
        "negative_controls": {
            "coherent_posed_shape_mutation": {
                "status": "PASS_MUTATION_DETECTED",
                "direction_signal_deg": 0.1573809848662001,
            }
        },
        "truth_boundary": {
            "post_skin_owner_frame_reconstruction_established": True,
            "technical_art_adopted_reconstruction": False,
            "animation_accepted": False,
            "runtime_or_controller_accepted": False,
            "shaded_visual_quality_accepted": False,
            "canon_claimed": False,
        },
    }


class DirectionFrameReconstructionContractTests(unittest.TestCase):
    def evaluate(self, receipt):
        return adopt_direction_frame_reconstruction_contract(
            receipt,
            exact_rigging_head=RIGGING_HEAD,
            exact_rigging_artifact_id=RIGGING_ARTIFACT_ID,
            exact_rigging_artifact_sha256=RIGGING_ARTIFACT_SHA256,
            exact_source_technical_art_head=SOURCE_TA_HEAD,
            exact_source_glb_sha256=SOURCE_GLB_SHA256,
            current_technical_art_head=CURRENT_TA_HEAD,
            current_uc_head=CURRENT_UC_HEAD,
            current_uc_codec_blob=CURRENT_UC_BLOB,
        )

    def test_exact_owner_pass_adopts_contract_but_keeps_runtime_hold(self):
        contract = self.evaluate(owner_receipt())
        self.assertEqual(contract["state"], PASS_STATE)
        self.assertTrue(contract["receiver_contract"]["portable_contract_adopted"])
        self.assertFalse(contract["receiver_contract"]["target_runtime_implemented"])
        self.assertFalse(contract["truth_boundary"]["raw_static_normal_tangent_direction_equivalence_established"])
        self.assertFalse(contract["universal_creation"]["product_modified"])
        with self.assertRaisesRegex(ValueError, "target runtime implementation is HOLD"):
            require_target_runtime_ready(contract)

    def test_historical_static_direction_hold_must_remain_explicit(self):
        value = owner_receipt()
        value["premise"]["static_direction_transport_gate"] = "PASS"
        with self.assertRaisesRegex(ValueError, "retained HOLD"):
            self.evaluate(value)

    def test_owner_direction_residual_over_bound_fails_closed(self):
        value = owner_receipt()
        value["reconstruction"]["maximum_owner_tangent_angle_deg"] = 0.01
        with self.assertRaisesRegex(ValueError, "owner tangent reconstruction exceeds"):
            self.evaluate(value)

    def test_owner_reconstruction_gate_must_be_pass(self):
        value = owner_receipt()
        value["reconstruction"]["gate"] = "HOLD"
        with self.assertRaisesRegex(ValueError, "owner reconstruction gate is not PASS"):
            self.evaluate(value)

    def test_sensitivity_control_must_detect_shape_mutation(self):
        value = owner_receipt()
        value["negative_controls"]["coherent_posed_shape_mutation"]["status"] = "HOLD"
        with self.assertRaisesRegex(ValueError, "sensitivity control"):
            self.evaluate(value)

    def test_owner_cannot_preclaim_technical_art_adoption(self):
        value = owner_receipt()
        value["truth_boundary"]["technical_art_adopted_reconstruction"] = True
        with self.assertRaisesRegex(ValueError, "must precede Technical Art adoption"):
            self.evaluate(value)

    def test_owner_cannot_smuggle_runtime_or_canon_acceptance(self):
        for key in ("runtime_or_controller_accepted", "canon_claimed"):
            with self.subTest(key=key):
                value = copy.deepcopy(owner_receipt())
                value["truth_boundary"][key] = True
                with self.assertRaisesRegex(ValueError, "overclaims"):
                    self.evaluate(value)


if __name__ == "__main__":
    unittest.main()
