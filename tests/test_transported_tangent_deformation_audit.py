from __future__ import annotations

import json
import math
import os
from pathlib import Path
import unittest

from axm_animal_design.transported_tangent_deformation_audit import (
    HOLD_STATE,
    PASS_STATE,
    TECHNICAL_ART_GLB_SHA256,
    _angle_deg,
    _decode_glb,
    _orthonormalize_tangent,
    _quat_rotate,
    inspect_transported_tangent_deformation,
)

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TransportedTangentDeformationAuditTest(unittest.TestCase):
    def test_quaternion_rotation_and_angle_are_stable(self):
        angle = math.radians(18.0)
        q = [0.0, math.sin(angle / 2.0), 0.0, math.cos(angle / 2.0)]
        rotated = _quat_rotate([1.0, 0.0, 0.0], q)
        self.assertAlmostEqual(rotated[0], math.cos(angle), places=12)
        self.assertAlmostEqual(rotated[2], -math.sin(angle), places=12)
        self.assertAlmostEqual(_angle_deg([1.0, 0.0, 0.0], rotated), 18.0, places=10)

    def test_orthonormalization_removes_normal_component(self):
        normal = [0.0, 1.0, 0.0]
        tangent = _orthonormalize_tangent([1.0, 0.2, 0.0], normal)
        self.assertAlmostEqual(sum(a * b for a, b in zip(normal, tangent)), 0.0, places=12)
        self.assertAlmostEqual(math.sqrt(sum(value * value for value in tangent)), 1.0, places=12)

    @unittest.skipUnless(
        os.environ.get("AXM_TA_GLB")
        and os.environ.get("AXM_TA_RECEIPT")
        and os.environ.get("AXM_RIG_PLAN")
        and os.environ.get("AXM_WEIGHTING_PROFILE"),
        "exact retained Technical Art artifact and Rigging donor are not mounted",
    )
    def test_exact_retained_transport_is_audited_without_source_or_rig_rewrite(self):
        glb_path = Path(os.environ["AXM_TA_GLB"])
        receipt_path = Path(os.environ["AXM_TA_RECEIPT"])
        glb = glb_path.read_bytes()
        decoded = _decode_glb(glb)
        self.assertEqual(len(decoded["ROTATIONS"]), 41)
        self.assertEqual(len(decoded["POSITION"]), 84)

        record = inspect_transported_tangent_deformation(
            _load(ROOT / "examples" / "quadruped_neutral_001.json"),
            _load(ROOT / "examples" / "quadruped_elbow_source_successor_003.json"),
            _load(ROOT / "examples" / "quadruped_elbow_bilateral_successor_003.json"),
            _load(Path(os.environ["AXM_RIG_PLAN"])),
            _load(Path(os.environ["AXM_WEIGHTING_PROFILE"])),
            _load(receipt_path),
            glb,
        )
        self.assertIn(record["state"], {PASS_STATE, HOLD_STATE})
        self.assertEqual(record["technical_art"]["glb_sha256"], TECHNICAL_ART_GLB_SHA256)
        self.assertEqual(record["position_uv_handedness"]["gate"], "PASS")
        self.assertEqual(record["negative_controls"]["child_weight_mutation"]["status"], "PASS_MUTATION_DETECTED")
        self.assertFalse(record["truth_boundary"]["animation_accepted"])
        self.assertFalse(record["truth_boundary"]["runtime_or_controller_accepted"])


if __name__ == "__main__":
    unittest.main()
