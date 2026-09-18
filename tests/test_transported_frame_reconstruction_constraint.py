from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from axm_animal_design.transported_frame_reconstruction_constraint import (
    PASS_STATE,
    _target_position_to_source,
    inspect_post_skin_owner_frame_reconstruction,
)

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TransportedFrameReconstructionConstraintTest(unittest.TestCase):
    def test_target_position_inverse_matches_animal_to_uc_boundary(self):
        source = [1.25, -0.75, 2.5]
        target = [-source[1], source[2], source[0]]
        reconstructed = _target_position_to_source(target)
        self.assertEqual(reconstructed, source)

    @unittest.skipUnless(
        os.environ.get("AXM_TA_GLB")
        and os.environ.get("AXM_TA_RECEIPT")
        and os.environ.get("AXM_RIG_PLAN")
        and os.environ.get("AXM_WEIGHTING_PROFILE"),
        "exact retained Technical Art artifact and Rigging donor are not mounted",
    )
    def test_exact_transported_positions_reconstruct_owner_direction_frame(self):
        record = inspect_post_skin_owner_frame_reconstruction(
            _load(ROOT / "examples" / "quadruped_neutral_001.json"),
            _load(ROOT / "examples" / "quadruped_elbow_source_successor_003.json"),
            _load(ROOT / "examples" / "quadruped_elbow_bilateral_successor_003.json"),
            _load(Path(os.environ["AXM_RIG_PLAN"])),
            _load(Path(os.environ["AXM_WEIGHTING_PROFILE"])),
            _load(Path(os.environ["AXM_TA_RECEIPT"])),
            Path(os.environ["AXM_TA_GLB"]).read_bytes(),
        )
        self.assertEqual(record["state"], PASS_STATE)
        self.assertEqual(record["premise"]["static_direction_transport_gate"], "HOLD")
        self.assertEqual(record["reconstruction"]["gate"], "PASS")
        self.assertEqual(
            record["negative_controls"]["coherent_posed_shape_mutation"]["status"],
            "PASS_MUTATION_DETECTED",
        )
        truth = record["truth_boundary"]
        self.assertTrue(truth["post_skin_owner_frame_reconstruction_established"])
        self.assertFalse(truth["technical_art_adopted_reconstruction"])
        self.assertFalse(truth["animation_accepted"])
        self.assertFalse(truth["runtime_or_controller_accepted"])


if __name__ == "__main__":
    unittest.main()
