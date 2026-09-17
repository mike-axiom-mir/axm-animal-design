from __future__ import annotations

import copy
import unittest

from axm_animal_design.uc_direction_frame_target_host_adapter import (
    ADOPTION_SCHEMA,
    ADOPTION_STATE,
    KEY_COUNT,
    PACKET_STATE,
    RENDER_VERTEX_COUNT,
    TRIANGLE_COUNT,
    build_target_host_packet,
    require_runtime_product_ready,
)


class TargetHostDirectionFrameAdapterTests(unittest.TestCase):
    def contract(self):
        return {
            "schema": ADOPTION_SCHEMA,
            "state": ADOPTION_STATE,
            "owner_evidence": {"rigging_head": "r"},
            "source_transport": {"glb_sha256": "g"},
            "technical_art": {"owner_reconstruction_algorithm_copied": False},
            "universal_creation": {"product_modified": False},
            "receiver_contract": {
                "portable_contract_adopted": True,
                "target_runtime_implemented": False,
            },
            "truth_boundary": {
                "animal_domain_policy_moved_into_uc": False,
                "raw_static_normal_tangent_direction_equivalence_established": False,
            },
        }

    def frames(self):
        indices = [value % RENDER_VERTEX_COUNT for value in range(TRIANGLE_COUNT * 3)]
        rows = []
        for index in range(KEY_COUNT):
            rows.append(
                {
                    "sample_index": index,
                    "time_seconds": index / 40.0,
                    "angle_deg": float(index),
                    "positions": [[0.0, 0.0, 0.0] for _ in range(RENDER_VERTEX_COUNT)],
                    "normals": [[0.0, 1.0, 0.0] for _ in range(RENDER_VERTEX_COUNT)],
                    "tangents": [[1.0, 0.0, 0.0, -1.0] for _ in range(RENDER_VERTEX_COUNT)],
                    "texcoords": [[0.0, 0.0] for _ in range(RENDER_VERTEX_COUNT)],
                    "indices": list(indices),
                    "uv_split_position_residual_m": 0.0,
                }
            )
        return rows

    def inspection(self):
        return {
            "pass": True,
            "vertices": RENDER_VERTEX_COUNT,
            "triangles": TRIANGLE_COUNT,
            "weightSumsPass": True,
            "jointIndicesPass": True,
            "deformation": {"pass": True},
        }

    def build(self, contract=None, frames=None):
        return build_target_host_packet(
            contract or self.contract(),
            frames=frames or self.frames(),
            exact_technical_art_head="ta",
            exact_source_glb_sha256="g",
            exact_rigging_head="r",
            exact_rigging_reconstruction_module_blob="blob",
            current_uc_head="uc",
            current_uc_codec_blob="codec",
            current_uc_inspection=self.inspection(),
        )

    def test_builds_all_key_reference_packet_without_runtime_promotion(self):
        packet = self.build()
        self.assertEqual(packet["state"], PACKET_STATE)
        self.assertEqual(len(packet["frames"]), KEY_COUNT)
        self.assertTrue(packet["truth_boundary"]["technical_art_target_host_reference_implemented"])
        self.assertFalse(packet["truth_boundary"]["runtime_product_implementation_established"])
        with self.assertRaisesRegex(ValueError, "Runtime product implementation is HOLD"):
            require_runtime_product_ready(packet)

    def test_rejects_silent_uc_domain_centralization(self):
        contract = self.contract()
        contract["truth_boundary"]["animal_domain_policy_moved_into_uc"] = True
        with self.assertRaisesRegex(ValueError, "Animal domain policy moved into UC"):
            self.build(contract=contract)

    def test_rejects_tangent_handedness_corruption(self):
        frames = self.frames()
        frames[17]["tangents"][3][3] = 0.0
        with self.assertRaisesRegex(ValueError, "tangent handedness"):
            self.build(frames=frames)

    def test_rejects_missing_authored_key(self):
        with self.assertRaisesRegex(ValueError, "all 41 authored keys"):
            self.build(frames=self.frames()[:-1])

    def test_rejects_current_uc_receiver_failure(self):
        inspection = self.inspection()
        inspection["deformation"]["pass"] = False
        with self.assertRaisesRegex(ValueError, "deformation observer failed"):
            build_target_host_packet(
                self.contract(),
                frames=self.frames(),
                exact_technical_art_head="ta",
                exact_source_glb_sha256="g",
                exact_rigging_head="r",
                exact_rigging_reconstruction_module_blob="blob",
                current_uc_head="uc",
                current_uc_codec_blob="codec",
                current_uc_inspection=inspection,
            )


if __name__ == "__main__":
    unittest.main()
